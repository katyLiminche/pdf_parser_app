"""
Специальный парсер для извлечения товарных позиций из таблиц
"""

import re
import logging
from typing import List, Dict, Any, Optional
import pandas as pd

logger = logging.getLogger(__name__)

class TableExtractor:
    """Специальный парсер для извлечения товарных позиций из таблиц"""
    
    def __init__(self):
        # Паттерны для определения товарных позиций
        self.product_patterns = [
            r'кабель.*силовой',
            r'кабель.*провод',
            r'сип-\d+',
            r'ввг',
            r'ппг',
            r'перевозка',
            r'транспорт',
            r'доставка',
            r'услуги',
            r'работы'
        ]
        
        # Слова для исключения служебной информации
        self.exclude_words = [
            'инн', 'кпп', 'счет', 'банк', 'бик', 'р/с', 'к/с', 'получатель', 'плательщик',
            'оплата', 'платеж', 'договор', 'счет на оплату', 'коммерческое предложение',
            'итого', 'всего', 'сумма', 'назначение', 'важно', 'примечание', 'примечания',
            'подготовлено', 'для', 'от', 'дата', 'номер', 'адрес', 'телефон', 'email',
            'россия', 'область', 'край', 'город', 'улица', 'дом', 'корпус', 'комната',
            'почтовое', 'индекс', 'код', 'вид', 'срок', 'плат', 'наз', 'пл', 'очер'
        ]
    
    def extract_items_from_tables(self, tables: List[pd.DataFrame]) -> List[Dict[str, Any]]:
        """Извлекает товарные позиции из таблиц"""
        items = []
        
        for table_idx, table in enumerate(tables):
            try:
                table_items = self._extract_from_table(table, table_idx)
                items.extend(table_items)
            except Exception as e:
                logger.warning(f"Ошибка извлечения из таблицы {table_idx}: {e}")
                continue
        
        return items
    
    def _extract_from_table(self, table: pd.DataFrame, table_idx: int) -> List[Dict[str, Any]]:
        """Извлекает товарные позиции из одной таблицы"""
        items = []
        
        # Определяем структуру таблицы
        column_mapping = self._identify_columns(table)
        
        if not column_mapping:
            logger.debug(f"Не удалось определить структуру таблицы {table_idx}")
            return items
        
        # Обрабатываем строки таблицы
        for row_idx, row in table.iterrows():
            try:
                # Пропускаем заголовки
                if self._is_header_row(row):
                    continue
                
                # Извлекаем товарную позицию
                item = self._extract_item_from_row(row, column_mapping, table_idx, row_idx)
                if item and self._is_valid_product(item):
                    items.append(item)
                    
            except Exception as e:
                logger.debug(f"Ошибка обработки строки {row_idx}: {e}")
                continue
        
        return items
    
    def _identify_columns(self, table: pd.DataFrame) -> Optional[Dict[str, int]]:
        """Определяет структуру колонок таблицы"""
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
                mapping = self._identify_by_position(columns)
            
            # Проверяем минимальные требования
            if 'name' in mapping and ('qty' in mapping or 'price' in mapping):
                return mapping
            
            return None
            
        except Exception as e:
            logger.debug(f"Ошибка определения колонок: {e}")
            return None
    
    def _identify_by_position(self, columns: List) -> Dict[str, int]:
        """Определяет колонки по позиции"""
        mapping = {}
        
        if len(columns) >= 7:
            # Стандартная структура: №, Наименование, Кол-во, Ед.изм., Цена, Сумма
            mapping = {
                'number': 0,
                'name': 1,
                'qty': 2,
                'unit': 3,
                'price': 4,
                'total': 5
            }
        elif len(columns) >= 6:
            # Упрощенная структура: №, Наименование, Кол-во, Ед.изм., Цена, Сумма
            mapping = {
                'number': 0,
                'name': 1,
                'qty': 2,
                'unit': 3,
                'price': 4,
                'total': 5
            }
        elif len(columns) >= 4:
            # Минимальная структура: Наименование, Кол-во, Цена, Сумма
            mapping = {
                'name': 0,
                'qty': 1,
                'price': 2,
                'total': 3
            }
        
        return mapping
    
    def _is_header_row(self, row: pd.Series) -> bool:
        """Проверяет, является ли строка заголовком"""
        try:
            first_cell = str(row.iloc[0]) if len(row) > 0 else ''
            header_indicators = ['№', 'номер', 'артикул', 'товары', 'количество', 'цена', 'сумма', 'наименование']
            return any(word in first_cell.lower() for word in header_indicators)
        except:
            return False
    
    def _extract_item_from_row(self, row: pd.Series, mapping: Dict[str, int], table_idx: int, row_idx: int) -> Optional[Dict[str, Any]]:
        """Извлекает товарную позицию из строки"""
        try:
            item = {}
            
            # Извлекаем значения из колонок
            for field, col_idx in mapping.items():
                if col_idx < len(row):
                    value = row.iloc[col_idx]
                    if pd.notna(value):
                        if field in ['qty', 'price', 'total']:
                            item[field] = self._parse_number(value)
                        else:
                            item[field] = str(value).strip()
                    else:
                        item[field] = None
            
            # Проверяем минимальные требования
            if not item.get('name') or item.get('qty') is None or item.get('price') is None:
                return None
            
            # Добавляем стандартные поля
            item['currency'] = 'RUB'
            item['source'] = f'table_{table_idx}_row_{row_idx}'
            item['confidence'] = 0.95
            
            # Вычисляем общую сумму если не указана
            if item.get('total') is None and item.get('qty') and item.get('price'):
                item['total'] = item['qty'] * item['price']
            
            return item
            
        except Exception as e:
            logger.debug(f"Ошибка извлечения элемента: {e}")
            return None
    
    def _is_valid_product(self, item: Dict[str, Any]) -> bool:
        """Проверяет, является ли элемент валидным товаром"""
        try:
            # Проверяем наличие обязательных полей
            if not item.get('name') or not item.get('qty') or not item.get('price'):
                return False
            
            # Исключаем служебную информацию
            name = str(item.get('name', '')).lower()
            
            # Проверяем, не содержит ли название служебные слова
            if any(word in name for word in self.exclude_words):
                return False
            
            # Проверяем, что название содержит буквы
            if not re.search(r'[а-яёa-z]{2,}', name, re.IGNORECASE):
                return False
            
            # Проверяем, что количество и цена положительные
            if item.get('qty', 0) <= 0 or item.get('price', 0) <= 0:
                return False
            
            # Проверяем, что название не слишком короткое
            if len(name.strip()) < 5:
                return False
            
            # Проверяем, что это похоже на товар
            if any(re.search(pattern, name, re.IGNORECASE) for pattern in self.product_patterns):
                return True
            
            # Если не похоже на товар, но содержит технические характеристики
            if re.search(r'\d+[х×]\d+', name) or re.search(r'\d+[кмлшт]', name):
                return True
            
            return False
            
        except Exception as e:
            logger.debug(f"Ошибка валидации товара: {e}")
            return False
    
    def _parse_number(self, value: Any) -> Optional[float]:
        """Парсит числа с поддержкой русских форматов"""
        if pd.isna(value):
            return None
        
        try:
            if isinstance(value, (int, float)):
                return float(value)
            
            value_str = str(value).strip()
            value_str = re.sub(r'[^\d\.,\s-]', '', value_str)
            
            if ',' in value_str and '.' in value_str:
                value_str = value_str.replace(',', '')
            elif ',' in value_str:
                if value_str.count(',') == 1 and len(value_str.split(',')[-1]) <= 2:
                    value_str = value_str.replace(',', '.')
                else:
                    value_str = value_str.replace(',', '')
            
            value_str = value_str.replace(' ', '')
            return float(value_str) if value_str else None
            
        except (ValueError, TypeError):
            return None
