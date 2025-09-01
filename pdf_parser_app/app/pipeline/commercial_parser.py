"""
Специализированный парсер для коммерческих предложений
"""

import re
import logging
from typing import List, Dict, Any, Optional
import pandas as pd

logger = logging.getLogger(__name__)

class CommercialProposalParser:
    """Парсер для коммерческих предложений поставщиков"""
    
    def __init__(self):
        # Паттерны для заголовков коммерческих предложений
        self.header_patterns = {
            'number': ['№', 'номер', 'n', 'number', 'позиция'],
            'name': ['наименование', 'название', 'описание', 'товар', 'name', 'description'],
            'qty': ['кол-во', 'количество', 'qty', 'amount', 'объем'],
            'unit': ['ед', 'единица', 'изм', 'unit', 'measure'],
            'price': ['цена', 'стоимость', 'price', 'cost', 'тариф'],
            'total': ['сумма', 'итого', 'total', 'sum', 'стоимость']
        }
        
        # Паттерны для строк товаров
        self.item_patterns = [
            # Паттерн 1: номер + название + количество + единица + цена + сумма
            re.compile(
                r'^(?P<number>\d+)\s+(?P<name>[А-Яа-я\w\s\-\.\n]+?)\s+(?P<qty>[\d\s\.,]+)\s+(?P<unit>шт|кг|м|л|pcs|kg|m|l|шт\.|кг\.|м\.|л\.|тонн|тонны|штук|штуки)?\s+'
                r'(?P<price>[\d\s\.,]+)\s+(?P<total>[\d\s\.,]+)',
                re.IGNORECASE | re.MULTILINE
            )
        ]
    
    def parse_commercial_proposal(self, text: str, tables: List[pd.DataFrame] = None) -> List[Dict[str, Any]]:
        """
        Парсинг коммерческого предложения
        
        Args:
            text: Текст документа
            tables: Извлеченные таблицы
            
        Returns:
            Список позиций с данными
        """
        items = []
        
        # Сначала пробуем парсить таблицы
        if tables:
            table_items = self._parse_commercial_tables(tables)
            items.extend(table_items)
            logger.info(f"Распарсено {len(table_items)} позиций из таблиц")
        
        # Затем парсим текст
        if text:
            text_items = self._parse_commercial_text(text)
            items.extend(text_items)
            logger.info(f"Распарсено {len(text_items)} позиций из текста")
        
        # Убираем дубликаты и валидируем
        unique_items = self._deduplicate_items(items)
        valid_items = [item for item in unique_items if self._validate_commercial_item(item)]
        
        logger.info(f"Всего валидных позиций: {len(valid_items)}")
        return valid_items
    
    def _parse_commercial_tables(self, tables: List[pd.DataFrame]) -> List[Dict[str, Any]]:
        """Парсинг таблиц коммерческого предложения"""
        items = []
        
        for table_idx, table in enumerate(tables):
            try:
                # Определяем структуру таблицы
                column_mapping = self._identify_commercial_columns(table.columns)
                
                logger.info(f"Таблица {table_idx}: найдено mapping: {column_mapping}")
                
                if column_mapping:
                    # Парсим с известной структурой
                    logger.info(f"Используем mapping для таблицы {table_idx}")
                    table_items = self._parse_table_with_mapping(table, column_mapping, table_idx)
                    items.extend(table_items)
                else:
                    # Пробуем определить структуру по содержимому
                    logger.info(f"Используем fallback для таблицы {table_idx}")
                    table_items = self._parse_table_by_content(table, table_idx)
                    items.extend(table_items)
                    
            except Exception as e:
                logger.warning(f"Ошибка парсинга таблицы {table_idx}: {e}")
                continue
        
        return items
    
    def _identify_commercial_columns(self, columns: pd.Index) -> Optional[Dict[str, int]]:
        """Определение колонок для коммерческого предложения"""
        mapping = {}
        
        # Принудительно используем mapping по позиции для больших таблиц
        if len(columns) >= 11:
            return self._identify_columns_by_position(columns)
        
        for col_idx, col_name in enumerate(columns):
            col_name_str = str(col_name).lower().strip()
            
            # Очищаем название колонки
            col_name_str = re.sub(r'[^\w\s]', ' ', col_name_str)
            col_name_str = ' '.join(col_name_str.split())
            
            # Проверяем паттерны
            for field, patterns in self.header_patterns.items():
                for pattern in patterns:
                    if pattern.lower() in col_name_str:
                        mapping[field] = col_idx
                        break
                if field in mapping:
                    break
        
        # Если не удалось определить по паттернам, используем эвристики
        if not mapping:
            mapping = self._identify_columns_by_position(columns)
        
        # Проверяем минимальные требования
        if 'name' in mapping and len(mapping) >= 2:
            return mapping
        
        return None
    
    def _identify_columns_by_position(self, columns: pd.Index) -> Dict[str, int]:
        """Определение колонок по позиции"""
        mapping = {}
        
        if len(columns) >= 11:
            # Структура из реального PDF: № | Наименование | Кол-во | Ед.изм | Цена | Сумма
            mapping['number'] = 0
            mapping['name'] = 1
            mapping['qty'] = 5      # Кол-во
            mapping['unit'] = 6     # Ед. изм.
            mapping['price'] = 8    # Цена (без НДС)
            mapping['total'] = 10   # Сумма (с НДС)
        elif len(columns) >= 6:
            # Типичная структура: № | Наименование | Кол-во | Ед.изм | Цена | Сумма
            mapping['number'] = 0
            mapping['name'] = 1
            mapping['qty'] = 2
            mapping['unit'] = 3
            mapping['price'] = 4
            mapping['total'] = 5
        elif len(columns) >= 4:
            # Минимальная структура: Наименование | Кол-во | Цена | Сумма
            mapping['name'] = 0
            mapping['qty'] = 1
            mapping['price'] = 2
            mapping['total'] = 3
        
        return mapping
    
    def _parse_table_with_mapping(self, table: pd.DataFrame, mapping: Dict[str, int], table_idx: int) -> List[Dict[str, Any]]:
        """Парсинг таблицы с известной структурой"""
        items = []
        
        for row_idx, row in table.iterrows():
            try:
                # Проверяем, является ли строка заголовком
                # Заголовок обычно содержит слова "Наименование", "Кол-во", "Цена" и т.д.
                first_cell = str(row.iloc[0]) if len(row) > 0 else ''
                if any(word in first_cell.lower() for word in ['наименование', 'кол-во', 'цена', 'сумма', '№']):
                    continue
                
                # Получаем значения из колонок
                name = str(row.iloc[mapping.get('name', 0)]) if 'name' in mapping else ''
                qty = self._parse_number(row.iloc[mapping.get('qty', 1)]) if 'qty' in mapping else 1.0
                unit = str(row.iloc[mapping.get('unit', 2)]) if 'unit' in mapping else ''
                price = self._parse_number(row.iloc[mapping.get('price', 3)]) if 'price' in mapping else 0.0
                total = self._parse_number(row.iloc[mapping.get('total', 4)]) if 'total' in mapping else None
                
                # Пропускаем пустые строки
                if not name.strip() or name.strip() in ['', 'nan', 'None']:
                    continue
                
                # Пропускаем служебные строки
                if self._is_service_row(name):
                    continue
                
                # Очищаем название от лишних символов
                name = self._clean_name(name)
                
                item = {
                    'name': name,
                    'qty': qty,
                    'unit': unit.strip() if unit else '',
                    'price': price,
                    'currency': 'RUB',
                    'total': total,
                    'supplier': '',
                    'source': f'table_{table_idx}_row_{row_idx}',
                    'confidence': 0.95
                }
                
                # Вычисляем общую сумму если не указана
                if item['total'] is None and item['qty'] and item['price']:
                    item['total'] = item['qty'] * item['price']
                
                # Валидируем элемент
                if self._validate_commercial_item(item):
                    items.append(item)
                
            except Exception as e:
                logger.debug(f"Ошибка парсинга строки {row_idx}: {e}")
                continue
        
        return items
    
    def _parse_table_by_content(self, table: pd.DataFrame, table_idx: int) -> List[Dict[str, Any]]:
        """Парсинг таблицы по содержимому (fallback)"""
        items = []
        
        for row_idx, row in table.iterrows():
            # Пропускаем заголовки
            if row_idx == 0:
                continue
            
            # Получаем значения из колонок
            row_values = []
            for cell in row:
                if pd.notna(cell) and str(cell).strip():
                    row_values.append(str(cell).strip())
            
            # Если есть достаточно данных, пытаемся распарсить
            if len(row_values) >= 4:
                try:
                    # Пытаемся определить структуру по содержимому
                    item = self._parse_table_row_values(row_values, table_idx, row_idx)
                    if item:
                        items.append(item)
                except Exception as e:
                    logger.debug(f"Ошибка парсинга строки таблицы {row_idx}: {e}")
                    continue
        
        return items
    
    def _parse_table_row_values(self, values: List[str], table_idx: int, row_idx: int) -> Optional[Dict[str, Any]]:
        """Парсинг значений строки таблицы"""
        if len(values) < 4:
            return None
        
        # Анализируем значения для определения структуры
        # Первая колонка - обычно номер позиции
        # Вторая колонка - название товара
        # Третья колонка - количество
        # Четвертая колонка - единица измерения
        # Пятая колонка - цена
        # Шестая колонка - сумма
        
        try:
            # Проверяем, что первая колонка - это номер
            if not re.match(r'^\d+$', values[0]):
                return None
            
            # Название товара
            name = values[1] if len(values) > 1 else ''
            if not name or self._is_service_row(name):
                return None
            
            # Ищем количество в следующих колонках
            qty = None
            qty_idx = None
            for i in range(2, min(5, len(values))):
                if values[i] and re.search(r'\d', values[i]):
                    qty = self._parse_number(values[i])
                    if qty is not None:
                        qty_idx = i
                        break
            
            if qty is None:
                return None
            
            # Ищем единицу измерения
            unit = ""
            if qty_idx + 1 < len(values):
                unit = values[qty_idx + 1]
            
            # Ищем цену в следующих колонках
            price = None
            for i in range(qty_idx + 2, min(qty_idx + 4, len(values))):
                if i < len(values) and values[i] and re.search(r'\d', values[i]):
                    price = self._parse_number(values[i])
                    if price is not None:
                        break
            
            if price is None:
                return None
            
            # Ищем сумму в последних колонках
            total = None
            for i in range(len(values) - 2, len(values)):
                if i >= 0 and values[i] and re.search(r'\d', values[i]):
                    total = self._parse_number(values[i])
                    if total is not None and total != price and total != qty:
                        break
            
            # Очищаем название
            name = self._clean_name(name)
            
            item = {
                'name': name,
                'qty': qty,
                'unit': unit.strip() if unit else '',
                'price': price,
                'currency': 'RUB',
                'total': total if total else qty * price,
                'supplier': '',
                'source': f'table_{table_idx}_row_{row_idx}',
                'confidence': 0.8
            }
            
            # Валидируем элемент
            if self._validate_commercial_item(item):
                return item
            
        except Exception as e:
            logger.debug(f"Ошибка парсинга значений строки: {e}")
        
        return None
    
    def _parse_commercial_text(self, text: str) -> List[Dict[str, Any]]:
        """Парсинг текста коммерческого предложения"""
        items = []
        lines = text.split('\n')
        
        for line_idx, line in enumerate(lines):
            line = line.strip()
            if not line or len(line) < 10:
                continue
            
            # Пропускаем заголовки и служебные строки
            if self._is_header_line(line) or self._is_service_line(line):
                continue
            
            # Пропускаем строки с только цифрами или пустые
            if re.match(r'^[\d\s\.,]+$', line) or not re.search(r'[а-яёa-z]', line, re.IGNORECASE):
                continue
            
            # Пропускаем строки с суммами итого
            if re.search(r'итого|всего|сумма.*руб', line.lower()):
                continue
            
            # Пытаемся распарсить строку как товарную
            parsed_item = self._parse_commercial_line(line)
            if parsed_item:
                parsed_item['source'] = f'text_line_{line_idx}'
                parsed_item['confidence'] = 0.7
                items.append(parsed_item)
        
        return items
    
    def _parse_commercial_line(self, line: str) -> Optional[Dict[str, Any]]:
        """Парсинг одной строки коммерческого предложения"""
        for pattern in self.item_patterns:
            match = pattern.search(line)
            if match:
                try:
                    name = match.group('name').strip()
                    qty = self._parse_number(match.group('qty'))
                    unit = match.group('unit') or ''
                    price = self._parse_number(match.group('price'))
                    total = self._parse_number(match.group('total'))
                    
                    # Очищаем название
                    name = self._clean_name(name)
                    
                    item = {
                        'name': name,
                        'qty': qty,
                        'unit': unit,
                        'price': price,
                        'currency': 'RUB',
                        'total': total if total else qty * price,
                        'supplier': '',
                        'source': 'regex_match',
                        'confidence': 0.85
                    }
                    
                    # Валидируем элемент
                    if self._validate_commercial_item(item):
                        return item
                        
                except Exception as e:
                    logger.debug(f"Ошибка парсинга строки с паттерном: {e}")
                    continue
        
        return None
    
    def _clean_name(self, name: str) -> str:
        """Очистка названия товара"""
        # Убираем лишние пробелы и переносы строк
        name = re.sub(r'\s+', ' ', name)
        name = re.sub(r'\n+', ' ', name)
        name = name.strip()
        
        # Убираем технические обозначения в начале
        name = re.sub(r'^[А-Я]{2,}-\d+[х×]\d+[-\d\.]*\s*ТУ\s*', '', name)
        
        return name
    
    def _is_header_line(self, line: str) -> bool:
        """Проверка, является ли строка заголовком"""
        header_indicators = [
            'наименование', 'название', 'количество', 'кол-во', 'цена', 'стоимость',
            'единица', 'валюта', 'сумма', 'итого', 'поставщик', 'коммерческое'
        ]
        
        line_lower = line.lower()
        return any(indicator in line_lower for indicator in header_indicators)
    
    def _is_service_line(self, line: str) -> bool:
        """Проверка, является ли строка служебной"""
        service_indicators = [
            'итого', 'всего', 'сумма', 'контракт', 'договор', 'счет', 'фактура',
            'поставщик:', 'покупатель:', 'дата:', 'номер:', 'подготовлено:', 'для:'
        ]
        
        line_lower = line.lower()
        return any(indicator in line_lower for indicator in service_indicators)
    
    def _is_service_row(self, name: str) -> bool:
        """Проверка, является ли строка служебной"""
        service_indicators = [
            'итого', 'всего', 'сумма', 'наименований', 'наименования',
            'корпус', 'комната', 'дом', 'шоссе', 'указанные', 'цены',
            'скидки', 'действуют', 'апреля', 'года', 'подготовлено'
        ]
        
        name_lower = name.lower()
        return any(indicator in name_lower for indicator in service_indicators)
    
    def _parse_number(self, value: Any) -> Optional[float]:
        """Парсинг чисел с поддержкой русских форматов"""
        if pd.isna(value):
            return None
        
        try:
            if isinstance(value, (int, float)):
                return float(value)
            
            # Преобразуем в строку и очищаем
            value_str = str(value).strip()
            
            # Убираем лишние символы
            value_str = re.sub(r'[^\d\.,\s-]', '', value_str)
            
            # Обрабатываем разделители
            if ',' in value_str and '.' in value_str:
                # Формат: 1,234.56
                value_str = value_str.replace(',', '')
            elif ',' in value_str:
                # Формат: 1,23 или 1 234,56
                if value_str.count(',') == 1 and len(value_str.split(',')[-1]) <= 2:
                    # Вероятно десятичный разделитель
                    value_str = value_str.replace(',', '.')
                else:
                    # Вероятно разделитель тысяч
                    value_str = value_str.replace(',', '')
            
            # Убираем пробелы
            value_str = value_str.replace(' ', '')
            
            return float(value_str) if value_str else None
            
        except (ValueError, TypeError):
            return None
    
    def _validate_commercial_item(self, item: Dict[str, Any]) -> bool:
        """Валидация элемента коммерческого предложения"""
        try:
            # Проверяем наличие обязательных полей
            if not item.get('name') or not item.get('qty') or not item.get('price'):
                return False
            
            # Исключаем служебную информацию
            name = str(item.get('name', '')).lower()
            
            # Список служебных слов для исключения
            service_words = [
                'инн', 'кпп', 'счет', 'банк', 'бик', 'р/с', 'к/с', 'получатель', 'плательщик',
                'оплата', 'платеж', 'договор', 'счет на оплату', 'коммерческое предложение',
                'итого', 'всего', 'сумма', 'назначение', 'важно', 'примечание', 'примечания',
                'подготовлено', 'для', 'от', 'дата', 'номер', 'адрес', 'телефон', 'email',
                'россия', 'область', 'край', 'город', 'улица', 'дом', 'корпус', 'комната',
                'почтовое', 'индекс', 'код', 'вид', 'срок', 'плат', 'наз', 'пл', 'очер',
                'ту', 'технические', 'условия', 'сертификат', 'соответствия'
            ]
            
            # Проверяем, не содержит ли название служебные слова
            if any(word in name for word in service_words):
                return False
            
            # Проверяем, что название содержит буквы (не только цифры и символы)
            if not re.search(r'[а-яёa-z]{2,}', name, re.IGNORECASE):
                return False
            
            # Проверяем, что количество и цена положительные
            if item.get('qty', 0) <= 0 or item.get('price', 0) <= 0:
                return False
            
            # Проверяем, что название не слишком короткое
            if len(name.strip()) < 5:
                return False
            
            return True
            
        except Exception as e:
            logger.debug(f"Ошибка валидации элемента: {e}")
            return False
    
    def _deduplicate_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Удаление дубликатов по названию, количеству и цене"""
        seen = set()
        unique_items = []
        
        for item in items:
            # Ключ для дедупликации
            key = (
                item.get('name', '').lower().strip(), 
                item.get('qty'), 
                item.get('price')
            )
            
            if key not in seen:
                seen.add(key)
                unique_items.append(item)
        
        return unique_items
