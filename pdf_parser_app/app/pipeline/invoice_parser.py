"""
Специализированный парсер для счетов на оплату
"""

import re
import logging
from typing import List, Dict, Any, Optional
import pandas as pd

logger = logging.getLogger(__name__)

class InvoiceParser:
    """Парсер для счетов на оплату"""
    
    def __init__(self):
        # Паттерны для заголовков счетов
        self.header_patterns = {
            'number': ['№', 'номер', 'n', 'number', 'позиция'],
            'article': ['артикул', 'код', 'article', 'code', 'sku'],
            'name': ['товары', 'работы', 'услуги', 'наименование', 'описание', 'name', 'description'],
            'qty': ['количество', 'кол-во', 'qty', 'amount', 'объем'],
            'unit': ['ед', 'единица', 'изм', 'unit', 'measure'],
            'price': ['цена', 'стоимость', 'price', 'cost', 'тариф'],
            'total': ['сумма', 'итого', 'total', 'sum', 'стоимость']
        }
        
        # Паттерны для строк товаров
        self.item_patterns = [
            # Паттерн 1: номер + артикул + название + количество + единица + цена + сумма
            re.compile(
                r'^(?P<number>\d+)\s+(?P<article>[А-Яа-я\w\-\d]+)\s+(?P<name>[А-Яа-я\w\s\-\.\n]+?)\s+(?P<qty>[\d\s\.,]+)\s+(?P<unit>шт|кг|м|л|pcs|kg|m|l|шт\.|кг\.|м\.|л\.|тонн|тонны|штук|штуки|км)?\s+'
                r'(?P<price>[\d\s\.,]+)\s+(?P<total>[\d\s\.,]+)',
                re.IGNORECASE | re.MULTILINE
            )
        ]
    
    def parse_invoice(self, text: str, tables: List[pd.DataFrame] = None) -> List[Dict[str, Any]]:
        """
        Парсинг счета на оплату
        
        Args:
            text: Текст документа
            tables: Извлеченные таблицы
            
        Returns:
            Список позиций с данными
        """
        items = []
        
        # Сначала пробуем парсить таблицы
        if tables:
            table_items = self._parse_invoice_tables(tables)
            items.extend(table_items)
            logger.info(f"Распарсено {len(table_items)} позиций из таблиц")
        
        # Затем парсим текст
        if text:
            text_items = self._parse_invoice_text(text)
            items.extend(text_items)
            logger.info(f"Распарсено {len(text_items)} позиций из текста")
        
        # Убираем дубликаты и валидируем
        unique_items = self._deduplicate_items(items)
        valid_items = [item for item in unique_items if self._validate_invoice_item(item)]
        
        logger.info(f"Всего валидных позиций: {len(valid_items)}")
        return valid_items
    
    def _parse_invoice_tables(self, tables: List[pd.DataFrame]) -> List[Dict[str, Any]]:
        """Парсинг таблиц счета на оплату"""
        items = []
        
        for table_idx, table in enumerate(tables):
            try:
                # Определяем структуру таблицы
                column_mapping = self._identify_invoice_columns(table)
                
                if column_mapping:
                    # Парсим с известной структурой
                    table_items = self._parse_table_with_mapping(table, column_mapping, table_idx)
                    items.extend(table_items)
                else:
                    # Пробуем определить структуру по содержимому
                    table_items = self._parse_table_by_content(table, table_idx)
                    items.extend(table_items)
                    
            except Exception as e:
                logger.warning(f"Ошибка парсинга таблицы {table_idx}: {e}")
                continue
        
        return items
    
    def _identify_invoice_columns(self, table: pd.DataFrame) -> Optional[Dict[str, int]]:
        """Определение колонок для счетов на оплату"""
        try:
            columns = list(table.columns)
            mapping = {}
            
            # Ищем колонки по заголовкам
            for i, col in enumerate(columns):
                if pd.isna(col):
                    continue
                
                col_str = str(col).lower()
                
                # Номер позиции
                if any(word in col_str for word in ['№', 'номер', 'позиция']):
                    mapping['number'] = i
                
                # Артикул
                elif any(word in col_str for word in ['артикул', 'код', 'арт']):
                    mapping['article'] = i
                
                # Наименование
                elif any(word in col_str for word in ['наименование', 'товары', 'работы', 'услуги', 'название']):
                    mapping['name'] = i
                
                # Количество
                elif any(word in col_str for word in ['количество', 'кол-во', 'колво']):
                    mapping['qty'] = i
                
                # Единица измерения
                elif any(word in col_str for word in ['ед', 'единица', 'изм']):
                    mapping['unit'] = i
                
                # Цена
                elif any(word in col_str for word in ['цена', 'стоимость', 'руб']):
                    mapping['price'] = i
                
                # Сумма
                elif any(word in col_str for word in ['сумма', 'итого', 'всего']):
                    mapping['total'] = i
            
            # Если не нашли по заголовкам, пробуем по позиции
            if not mapping:
                mapping = self._identify_columns_by_position(columns)
            
            # Проверяем минимальные требования
            if 'name' in mapping and ('qty' in mapping or 'price' in mapping):
                return mapping
            
            return None
            
        except Exception as e:
            logger.debug(f"Ошибка определения колонок: {e}")
            return None
    
    def _identify_columns_by_position(self, columns: pd.Index) -> Dict[str, int]:
        """Определение колонок по позиции"""
        mapping = {}
        
        if len(columns) >= 10:
            # Структура из реального счета: № | Артикул | Товары | Количество | Ед.изм | Цена | Сумма | Срок поставки
            mapping['number'] = 0
            mapping['article'] = 1
            mapping['name'] = 2
            mapping['qty'] = 3
            mapping['unit'] = 4
            mapping['price'] = 5
            mapping['total'] = 6
        elif len(columns) >= 7:
            # Структура из реального счета: № | Артикул | Товары | Количество | Ед.изм | Цена | Сумма
            mapping['number'] = 0
            mapping['article'] = 1
            mapping['name'] = 2
            mapping['qty'] = 3
            mapping['unit'] = 4
            mapping['price'] = 5
            mapping['total'] = 6
        elif len(columns) >= 6:
            # Структура: № | Наименование | Кол-во | Ед.изм | Цена | Сумма
            mapping['number'] = 0
            mapping['name'] = 1
            mapping['qty'] = 2
            mapping['unit'] = 3
            mapping['price'] = 4
            mapping['total'] = 5
        elif len(columns) >= 5:
            # Минимальная структура: № | Наименование | Кол-во | Цена | Сумма
            mapping['number'] = 0
            mapping['name'] = 1
            mapping['qty'] = 2
            mapping['price'] = 3
            mapping['total'] = 4
        
        return mapping
    
    def _parse_table_with_mapping(self, table: pd.DataFrame, mapping: Dict[str, int], table_idx: int) -> List[Dict[str, Any]]:
        """Парсинг таблицы с известной структурой"""
        items = []
        
        for row_idx, row in table.iterrows():
            try:
                # Проверяем, является ли строка заголовком
                first_cell = str(row.iloc[0]) if len(row) > 0 else ''
                if any(word in first_cell.lower() for word in ['№', 'номер', 'артикул', 'товары', 'количество', 'цена', 'сумма']):
                    continue
                
                # Получаем значения из колонок
                number = str(row.iloc[mapping.get('number', 0)]) if 'number' in mapping else ''
                article = str(row.iloc[mapping.get('article', 1)]) if 'article' in mapping else ''
                name = str(row.iloc[mapping.get('name', 2)]) if 'name' in mapping else ''
                qty = self._parse_number(row.iloc[mapping.get('qty', 3)]) if 'qty' in mapping else 1.0
                unit = str(row.iloc[mapping.get('unit', 4)]) if 'unit' in mapping else ''
                price = self._parse_number(row.iloc[mapping.get('price', 5)]) if 'price' in mapping else 0.0
                total = self._parse_number(row.iloc[mapping.get('total', 6)]) if 'total' in mapping else None
                
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
                    'article': article.strip() if article else '',
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
                if self._validate_invoice_item(item):
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
            if len(row_values) >= 5:
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
        if len(values) < 5:
            return None
        
        # Анализируем значения для определения структуры
        # Первая колонка - обычно номер позиции
        # Вторая колонка - артикул/код
        # Третья колонка - название товара
        # Четвертая колонка - количество
        # Пятая колонка - единица измерения
        # Шестая колонка - цена
        # Седьмая колонка - сумма
        
        try:
            # Проверяем, что первая колонка - это номер
            if not re.match(r'^\d+$', values[0]):
                return None
            
            # Артикул
            article = values[1] if len(values) > 1 else ''
            
            # Название товара
            name = values[2] if len(values) > 2 else ''
            if not name or self._is_service_row(name):
                return None
            
            # Количество
            qty = self._parse_number(values[3]) if len(values) > 3 else None
            if qty is None:
                return None
            
            # Единица измерения
            unit = values[4] if len(values) > 4 else ''
            
            # Цена
            price = self._parse_number(values[5]) if len(values) > 5 else None
            if price is None:
                return None
            
            # Сумма
            total = self._parse_number(values[6]) if len(values) > 6 else None
            
            # Очищаем название
            name = self._clean_name(name)
            
            item = {
                'name': name,
                'article': article.strip() if article else '',
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
            if self._validate_invoice_item(item):
                return item
            
        except Exception as e:
            logger.debug(f"Ошибка парсинга значений строки: {e}")
        
        return None
    
    def _parse_invoice_text(self, text: str) -> List[Dict[str, Any]]:
        """Парсинг текста счета на оплату"""
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
            parsed_item = self._parse_invoice_line(line)
            if parsed_item:
                parsed_item['source'] = f'text_line_{line_idx}'
                parsed_item['confidence'] = 0.7
                items.append(parsed_item)
        
        return items
    
    def _parse_invoice_line(self, line: str) -> Optional[Dict[str, Any]]:
        """Парсинг одной строки счета на оплату"""
        for pattern in self.item_patterns:
            match = pattern.search(line)
            if match:
                try:
                    number = match.group('number').strip()
                    article = match.group('article') or ''
                    name = match.group('name').strip()
                    qty = self._parse_number(match.group('qty'))
                    unit = match.group('unit') or ''
                    price = self._parse_number(match.group('price'))
                    total = self._parse_number(match.group('total'))
                    
                    # Очищаем название
                    name = self._clean_name(name)
                    
                    item = {
                        'name': name,
                        'article': article,
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
                    if self._validate_invoice_item(item):
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
        
        return name
    
    def _is_header_line(self, line: str) -> bool:
        """Проверка, является ли строка заголовком"""
        header_indicators = [
            'наименование', 'название', 'количество', 'кол-во', 'цена', 'стоимость',
            'единица', 'валюта', 'сумма', 'итого', 'поставщик', 'счет', 'оплату'
        ]
        
        line_lower = line.lower()
        return any(indicator in line_lower for indicator in header_indicators)
    
    def _is_service_line(self, line: str) -> bool:
        """Проверка, является ли строка служебной"""
        service_indicators = [
            'итого', 'всего', 'сумма', 'контракт', 'договор', 'счет', 'фактура',
            'поставщик:', 'покупатель:', 'дата:', 'номер:', 'подготовлено:', 'для:',
            'инн', 'кпп', 'бик', 'р/с', 'банк', 'получатель', 'плательщик'
        ]
        
        line_lower = line.lower()
        return any(indicator in line_lower for indicator in service_indicators)
    
    def _is_service_row(self, name: str) -> bool:
        """Проверка, является ли строка служебной"""
        service_indicators = [
            'итого', 'всего', 'сумма', 'наименований', 'наименования',
            'корпус', 'комната', 'дом', 'шоссе', 'указанные', 'цены',
            'скидки', 'действуют', 'апреля', 'года', 'подготовлено',
            'инн', 'кпп', 'бик', 'р/с', 'банк', 'получатель', 'плательщик'
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
    
    def _validate_invoice_item(self, item: Dict[str, Any]) -> bool:
        """Валидация элемента счета на оплату"""
        # Должно быть название
        if not item.get('name') or len(item['name'].strip()) < 2:
            return False
        
        # Должно быть количество и цена
        if item.get('qty') is None or item.get('price') is None:
            return False
        
        # Количество и цена должны быть положительными
        if item['qty'] <= 0 or item['price'] <= 0:
            return False
        
        # Название не должно быть служебным
        if self._is_service_row(item['name']):
            return False
        
        # Дополнительная проверка: название должно содержать технические характеристики
        # Но делаем её более мягкой - достаточно наличия букв
        if not re.search(r'[а-яёa-z]', item['name'], re.IGNORECASE):
            return False
        
        return True
    
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
