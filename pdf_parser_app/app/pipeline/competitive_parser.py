"""
Специализированный парсер для конкурентной процедуры
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd

logger = logging.getLogger(__name__)

class CompetitiveParser:
    """Парсер для конкурентной процедуры закупок"""
    
    def __init__(self):
        # Паттерны для заголовков конкурентной процедуры
        self.header_patterns = {
            'name': [
                'наименование', 'название', 'товар', 'описание', 'name', 'description', 'item', 'product',
                'наименование товара', 'название товара', 'описание товара'
            ],
            'qty': [
                'количество', 'кол-во', 'кол', 'qty', 'quantity', 'amount', 'шт', 'объем',
                'количество товара', 'объем поставки'
            ],
            'unit': [
                'единица', 'ед.изм', 'ед', 'unit', 'measure', 'измерение',
                'единица измерения', 'ед. изм'
            ],
            'price': [
                'цена', 'стоимость', 'price', 'cost', 'rate', 'тариф',
                'цена за единицу', 'стоимость единицы', 'цена закупки'
            ],
            'currency': [
                'валюта', 'currency', 'curr', 'руб', 'usd', 'eur',
                'рубль', 'доллар', 'евро'
            ],
            'total': [
                'сумма', 'итого', 'total', 'sum', 'amount', 'стоимость',
                'общая сумма', 'стоимость позиции'
            ],
            'supplier': [
                'поставщик', 'supplier', 'vendor', 'компания', 'организация',
                'наименование поставщика'
            ]
        }
        
        # Паттерны для строк товаров
        self.item_patterns = [
            # Паттерн 1: название + количество + единица + цена + валюта
            re.compile(
                r'^(?P<name>[А-Яа-я\w\s\-\.]+?)\s+(?P<qty>[\d\s\.,]+)\s*(?P<unit>шт|кг|м|л|pcs|kg|m|l|шт\.|кг\.|м\.|л\.|тонн|тонны|штук|штуки)?\s+'
                r'(?P<price>[\d\s\.,]+)\s*(?P<currency>руб|₽|USD|EUR|руб\.|usd|eur|рублей|долларов|евро)?',
                re.IGNORECASE | re.MULTILINE
            ),
            
            # Паттерн 2: название + цена + валюта + количество + единица
            re.compile(
                r'^(?P<name>[А-Яа-я\w\s\-\.]+?)\s+(?P<price>[\d\s\.,]+)\s*(?P<currency>руб|₽|USD|EUR|руб\.|usd|eur)?\s+'
                r'(?P<qty>[\d\s\.,]+)\s*(?P<unit>шт|кг|м|л|pcs|kg|m|l|шт\.|кг\.|м\.|л\.|тонн|тонны|штук|штуки)?',
                re.IGNORECASE | re.MULTILINE
            ),
            
            # Паттерн 3: название + количество + цена (без единицы)
            re.compile(
                r'^(?P<name>[А-Яа-я\w\s\-\.]+?)\s+(?P<qty>[\d\s\.,]+)\s+(?P<price>[\d\s\.,]+)',
                re.IGNORECASE | re.MULTILINE
            ),
            
            # Паттерн 4: название + количество + единица + цена + сумма
            re.compile(
                r'^(?P<name>[А-Яа-я\w\s\-\.]+?)\s+(?P<qty>[\d\s\.,]+)\s*(?P<unit>шт|кг|м|л|pcs|kg|m|l|шт\.|кг\.|м\.|л\.|тонн|тонны|штук|штуки)?\s+'
                r'(?P<price>[\d\s\.,]+)\s+(?P<total>[\d\s\.,]+)',
                re.IGNORECASE | re.MULTILINE
            )
        ]
    
    def parse_competitive_document(self, text: str, tables: List[pd.DataFrame] = None) -> List[Dict[str, Any]]:
        """
        Парсинг документа конкурентной процедуры
        
        Args:
            text: Текст документа
            tables: Извлеченные таблицы
            
        Returns:
            Список позиций с данными
        """
        items = []
        
        # Сначала пробуем парсить таблицы
        if tables:
            table_items = self._parse_competitive_tables(tables)
            items.extend(table_items)
            logger.info(f"Распарсено {len(table_items)} позиций из таблиц")
        
        # Затем парсим текст
        if text:
            text_items = self._parse_competitive_text(text)
            items.extend(text_items)
            logger.info(f"Распарсено {len(text_items)} позиций из текста")
        
        # Убираем дубликаты и валидируем
        unique_items = self._deduplicate_items(items)
        valid_items = [item for item in unique_items if self._validate_competitive_item(item)]
        
        logger.info(f"Всего валидных позиций: {len(valid_items)}")
        return valid_items
    
    def _parse_competitive_tables(self, tables: List[pd.DataFrame]) -> List[Dict[str, Any]]:
        """Парсинг таблиц конкурентной процедуры"""
        items = []
        
        for table_idx, table in enumerate(tables):
            try:
                # Определяем структуру таблицы
                column_mapping = self._identify_competitive_columns(table.columns)
                
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
    
    def _identify_competitive_columns(self, columns: pd.Index) -> Optional[Dict[str, int]]:
        """Определение колонок для конкурентной процедуры"""
        mapping = {}
        
        for col_idx, col_name in enumerate(columns):
            col_name_str = str(col_name).lower().strip()
            
            # Очищаем название колонки от лишних символов
            col_name_str = re.sub(r'[^\w\s]', ' ', col_name_str)
            col_name_str = ' '.join(col_name_str.split())
            
            for field, patterns in self.header_patterns.items():
                for pattern in patterns:
                    if pattern.lower() in col_name_str:
                        mapping[field] = col_idx
                        break
                if field in mapping:
                    break
        
        # Если не удалось определить по паттернам, пробуем по содержимому
        if not mapping:
            mapping = self._identify_columns_by_content(columns)
        
        # Проверяем минимальные требования
        if 'name' in mapping and len(mapping) >= 2:
            return mapping
        
        return None
    
    def _identify_columns_by_content(self, columns: pd.Index) -> Dict[str, int]:
        """Определение колонок по содержимому"""
        mapping = {}
        
        # Простые эвристики для определения колонок
        for col_idx, col_name in enumerate(columns):
            col_name_str = str(col_name).lower().strip()
            
            # Номер позиции
            if any(word in col_name_str for word in ['№', 'номер', 'n', 'number']):
                continue  # Пропускаем номер позиции
            
            # Наименование (первая колонка с текстом)
            if 'name' not in mapping and any(word in col_name_str for word in ['наимен', 'название', 'описание', 'товар']):
                mapping['name'] = col_idx
            
            # Количество
            elif 'qty' not in mapping and any(word in col_name_str for word in ['кол-во', 'количество', 'qty', 'amount']):
                mapping['qty'] = col_idx
            
            # Единица измерения
            elif 'unit' not in mapping and any(word in col_name_str for word in ['ед', 'единица', 'изм', 'unit']):
                mapping['unit'] = col_idx
            
            # Цена
            elif 'price' not in mapping and any(word in col_name_str for word in ['цена', 'стоимость', 'price', 'cost']):
                mapping['price'] = col_idx
            
            # Сумма
            elif 'total' not in mapping and any(word in col_name_str for word in ['сумма', 'итого', 'total', 'sum']):
                mapping['total'] = col_idx
        
        # Если не удалось определить, используем позиции по умолчанию
        if not mapping:
            if len(columns) >= 3:
                mapping['name'] = 1  # Вторая колонка (после номера)
                mapping['qty'] = 2   # Третья колонка
                mapping['price'] = 3 # Четвертая колонка
        
        return mapping
    
    def _parse_table_with_mapping(self, table: pd.DataFrame, mapping: Dict[str, int], table_idx: int) -> List[Dict[str, Any]]:
        """Парсинг таблицы с известной структурой"""
        items = []
        
        for row_idx, row in table.iterrows():
            try:
                # Пропускаем заголовки
                if row_idx == 0:
                    continue
                
                # Получаем значения из колонок
                name = str(row.iloc[mapping.get('name', 0)]) if 'name' in mapping else ''
                qty = self._parse_number(row.iloc[mapping.get('qty', 1)]) if 'qty' in mapping else 1.0
                unit = str(row.iloc[mapping.get('unit', 2)]) if 'unit' in mapping else ''
                price = self._parse_number(row.iloc[mapping.get('price', 3)]) if 'price' in mapping else 0.0
                currency = str(row.iloc[mapping.get('currency', 4)]) if 'currency' in mapping else 'RUB'
                total = self._parse_number(row.iloc[mapping.get('total', 5)]) if 'total' in mapping else None
                supplier = str(row.iloc[mapping.get('supplier', 6)]) if 'supplier' in mapping else ''
                
                # Пропускаем пустые строки
                if not name.strip() or name.strip() in ['', 'nan', 'None']:
                    continue
                
                # Пропускаем служебные строки
                if self._is_service_row(name):
                    continue
                
                item = {
                    'name': name.strip(),
                    'qty': qty,
                    'unit': unit.strip() if unit else '',
                    'price': price,
                    'currency': currency.strip() if currency else 'RUB',
                    'total': total,
                    'supplier': supplier.strip() if supplier else '',
                    'source': f'table_{table_idx}_row_{row_idx}',
                    'confidence': 0.95
                }
                
                # Вычисляем общую сумму если не указана
                if item['total'] is None and item['qty'] and item['price']:
                    item['total'] = item['qty'] * item['price']
                
                # Валидируем элемент
                if self._validate_competitive_item(item):
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
            if len(row_values) >= 3:
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
        if len(values) < 3:
            return None
        
        # Анализируем значения для определения структуры
        name = values[0]  # Первая колонка - обычно название
        
        # Ищем числа в остальных колонках
        numbers = []
        for value in values[1:]:
            num = self._parse_number(value)
            if num is not None:
                numbers.append(num)
        
        if len(numbers) < 2:
            return None
        
        # Определяем количество и цену
        if len(numbers) >= 2:
            qty = numbers[0]
            price = numbers[1]
            total = numbers[2] if len(numbers) >= 3 else qty * price
        else:
            return None
        
        # Определяем единицу измерения
        unit = ""
        for value in values[1:]:
            if any(u in value.lower() for u in ['шт', 'кг', 'м', 'л', 'pcs', 'kg', 'm', 'l']):
                unit = value
                break
        
        # Определяем валюту
        currency = "RUB"
        for value in values:
            if any(c in value.upper() for c in ['RUB', 'USD', 'EUR', 'РУБ', 'ДОЛЛ', 'ЕВРО']):
                currency = value.upper()
                break
        
        item = {
            'name': name,
            'qty': qty,
            'unit': unit,
            'price': price,
            'currency': currency,
            'total': total,
            'supplier': '',
            'source': f'table_{table_idx}_row_{row_idx}',
            'confidence': 0.8
        }
        
        # Валидируем элемент
        if self._validate_competitive_item(item):
            return item
        
        return None
    
    def _parse_competitive_text(self, text: str) -> List[Dict[str, Any]]:
        """Парсинг текста конкурентной процедуры"""
        items = []
        lines = text.split('\n')
        
        # Сначала пробуем парсить структурированный текст (Наименование: значение)
        structured_items = self._parse_structured_text(text)
        if structured_items:
            items.extend(structured_items)
            logger.info(f"Найдено {len(structured_items)} структурированных позиций")
        
        # Затем парсим обычные строки
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
            
            # Пытаемся распарсить строку как табличную
            table_item = self._parse_table_line(line, line_idx)
            if table_item:
                items.append(table_item)
                continue
            
            # Если не получилось как таблица, пробуем как простую строку
            parsed_item = self._parse_competitive_line(line)
            if parsed_item:
                parsed_item['source'] = f'text_line_{line_idx}'
                parsed_item['confidence'] = 0.7
                items.append(parsed_item)
        
        return items
    
    def _parse_structured_text(self, text: str) -> List[Dict[str, Any]]:
        """Парсинг структурированного текста (Наименование: значение)"""
        items = []
        
        # Разбиваем на блоки по пустым строкам
        blocks = re.split(r'\n\s*\n', text)
        
        for block in blocks:
            if not block.strip():
                continue
            
            # Парсим блок
            item = self._parse_structured_block(block)
            if item:
                item['source'] = 'structured_text'
                item['confidence'] = 0.9
                items.append(item)
        
        return items
    
    def _parse_structured_block(self, block: str) -> Optional[Dict[str, Any]]:
        """Парсинг блока структурированного текста"""
        lines = block.strip().split('\n')
        
        item_data = {}
        
        for line in lines:
            line = line.strip()
            if not line or ':' not in line:
                continue
            
            # Ищем пары ключ: значение
            if ':' in line:
                parts = line.split(':', 1)
                if len(parts) == 2:
                    key = parts[0].strip().lower()
                    value = parts[1].strip()
                    
                    # Определяем тип поля
                    if any(pattern in key for pattern in ['наименование', 'название', 'товар']):
                        item_data['name'] = value
                    elif any(pattern in key for pattern in ['количество', 'кол-во', 'кол', 'объем']):
                        item_data['qty'] = self._parse_number(value)
                    elif any(pattern in key for pattern in ['единица', 'ед.изм', 'ед']):
                        item_data['unit'] = value
                    elif any(pattern in key for pattern in ['цена', 'стоимость', 'тариф']):
                        item_data['price'] = self._parse_number(value)
                    elif any(pattern in key for pattern in ['валюта', 'currency']):
                        item_data['currency'] = value
                    elif any(pattern in key for pattern in ['сумма', 'итого', 'стоимость', 'общая']):
                        item_data['total'] = self._parse_number(value)
                    elif any(pattern in key for pattern in ['поставщик', 'supplier', 'компания']):
                        item_data['supplier'] = value
        
        # Проверяем минимальные требования
        if 'name' in item_data and 'qty' in item_data and 'price' in item_data:
            # Устанавливаем значения по умолчанию
            if 'unit' not in item_data:
                item_data['unit'] = ''
            if 'currency' not in item_data:
                item_data['currency'] = 'RUB'
            if 'total' not in item_data:
                item_data['total'] = item_data['qty'] * item_data['price']
            if 'supplier' not in item_data:
                item_data['supplier'] = ''
            
            return item_data
        
        return None
    
    def _parse_competitive_line(self, line: str) -> Optional[Dict[str, Any]]:
        """Парсинг одной строки конкурентной процедуры"""
        for pattern in self.item_patterns:
            match = pattern.search(line)
            if match:
                try:
                    # Извлекаем базовые данные
                    name = match.group('name').strip()
                    qty = self._parse_number(match.group('qty'))
                    unit = match.group('unit') or ''
                    price = self._parse_number(match.group('price'))
                    currency = match.group('currency') or 'RUB'
                    total = None
                    
                    # Если есть total в паттерне, извлекаем его
                    if 'total' in match.groupdict() and match.group('total'):
                        total = self._parse_number(match.group('total'))
                    
                    # Если total не найден, вычисляем
                    if total is None and qty and price:
                        total = qty * price
                    
                    # Очищаем название от лишних пробелов
                    name = ' '.join(name.split())
                    
                    # Очищаем единицу измерения
                    if unit:
                        unit = unit.strip()
                        # Убираем лишние символы из единицы
                        unit = re.sub(r'[^\w\.]', '', unit)
                    
                    item = {
                        'name': name,
                        'qty': qty,
                        'unit': unit,
                        'price': price,
                        'currency': currency,
                        'total': total,
                        'supplier': '',
                        'source': 'regex_match',
                        'confidence': 0.85
                    }
                    
                    # Валидируем элемент
                    if self._validate_competitive_item(item):
                        return item
                        
                except Exception as e:
                    logger.debug(f"Ошибка парсинга строки с паттерном: {e}")
                    continue
        
        return None
    
    def _is_header_line(self, line: str) -> bool:
        """Проверка, является ли строка заголовком"""
        header_indicators = [
            'наименование', 'название', 'количество', 'кол-во', 'цена', 'стоимость',
            'единица', 'валюта', 'сумма', 'итого', 'поставщик'
        ]
        
        line_lower = line.lower()
        return any(indicator in line_lower for indicator in header_indicators)
    
    def _is_service_line(self, line: str) -> bool:
        """Проверка, является ли строка служебной"""
        service_indicators = [
            'итого', 'всего', 'сумма', 'контракт', 'договор', 'счет', 'фактура',
            'поставщик:', 'покупатель:', 'дата:', 'номер:'
        ]
        
        line_lower = line.lower()
        return any(indicator in line_lower for indicator in service_indicators)
    
    def _is_service_row(self, name: str) -> bool:
        """Проверка, является ли строка служебной"""
        service_indicators = [
            'итого', 'всего', 'сумма', 'наименований', 'наименования',
            'корпус', 'комната', 'дом', 'шоссе', 'указанные', 'цены',
            'скидки', 'действуют', 'апреля', 'года'
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
    
    def _validate_competitive_item(self, item: Dict[str, Any]) -> bool:
        """Валидация элемента конкурентной процедуры"""
        # Должно быть название
        if not item.get('name') or len(item['name'].strip()) < 2:
            return False
        
        # Должно быть количество и цена
        if item.get('qty') is None or item.get('price') is None:
            return False
        
        # Количество и цена должны быть положительными
        if item['qty'] <= 0 or item['price'] <= 0:
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

    def _parse_table_line(self, line: str, line_idx: int) -> Optional[Dict[str, Any]]:
        """Парсинг строки как табличной (с разделением по пробелам)"""
        try:
            # Разбиваем строку по пробелам
            parts = line.split()
            if len(parts) < 3:
                return None
            
            # Ищем название (начинается с буквы)
            name_parts = []
            number_parts = []
            
            for part in parts:
                if re.match(r'^[а-яёa-z]', part, re.IGNORECASE):
                    name_parts.append(part)
                elif re.match(r'^[\d\.,]+$', part):
                    number_parts.append(part)
            
            if not name_parts or len(number_parts) < 2:
                return None
            
            # Собираем название
            name = ' '.join(name_parts)
            
            # Парсим числа
            qty = self._parse_number(number_parts[0])
            price = self._parse_number(number_parts[1])
            
            if qty is None or price is None:
                return None
            
            # Определяем единицу измерения
            unit = ""
            for part in parts:
                if any(u in part.lower() for u in ['шт', 'кг', 'м', 'л', 'pcs', 'kg', 'm', 'l']):
                    unit = part
                    break
            
            # Определяем валюту
            currency = "RUB"
            for part in parts:
                if any(c in part.upper() for c in ['RUB', 'USD', 'EUR', 'РУБ', 'ДОЛЛ', 'ЕВРО']):
                    currency = part.upper()
                    break
            
            # Вычисляем сумму
            total = qty * price
            
            item = {
                'name': name,
                'qty': qty,
                'unit': unit,
                'price': price,
                'currency': currency,
                'total': total,
                'supplier': '',
                'source': f'table_line_{line_idx}',
                'confidence': 0.8
            }
            
            # Валидируем элемент
            if self._validate_competitive_item(item):
                return item
            
        except Exception as e:
            logger.debug(f"Ошибка парсинга табличной строки: {e}")
        
        return None
