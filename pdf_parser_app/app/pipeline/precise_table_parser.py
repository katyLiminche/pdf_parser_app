"""
Точный парсер для извлечения товарных позиций из таблиц
"""

import re
import logging
from typing import List, Dict, Any, Optional
import pandas as pd

logger = logging.getLogger(__name__)

class PreciseTableParser:
    """Точный парсер для извлечения товарных позиций из таблиц"""
    
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
            'почтовое', 'индекс', 'код', 'вид', 'срок', 'плат', 'наз', 'пл', 'очер',
            'технические', 'условия', 'сертификат', 'соответствия'
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
        
        logger.info(f"Таблица {table_idx}: найдено mapping: {column_mapping}")
        
        if not column_mapping:
            logger.debug(f"Не удалось определить структуру таблицы {table_idx}")
            return items
        
        # Обрабатываем строки таблицы
        for row_idx, row in table.iterrows():
            try:
                # Отладка для файла "пример входных данных от поставщиков.pdf"
                if table_idx == 0 and row_idx < 3:  # Первые 3 строки первой таблицы
                    logger.info(f"Обработка строки {row_idx} таблицы {table_idx}")
                
                # Пропускаем заголовки и служебные строки
                is_header = self._is_header_row(row)
                is_service = self._is_service_row(row)
                
                if table_idx == 0 and row_idx < 3:  # Первые 3 строки первой таблицы
                    logger.info(f"Строка {row_idx}: is_header={is_header}, is_service={is_service}")
                    # Подробная отладка служебных слов
                    if is_service:
                        logger.info(f"  Подробная отладка служебных слов в строке {row_idx}:")
                        for cell_idx, cell in enumerate(row):
                            if pd.notna(cell):
                                cell_str = str(cell).lower()
                                for word in self.exclude_words:
                                    if word in cell_str:
                                        logger.info(f"    Колонка {cell_idx}: '{cell}' содержит служебное слово '{word}'")
                
                if is_header or is_service:
                    if table_idx == 0 and row_idx < 3:  # Первые 3 строки первой таблицы
                        logger.info(f"Строка {row_idx} пропущена (заголовок или служебная)")
                    logger.debug(f"Пропускаем строку {row_idx} (заголовок или служебная)")
                    continue
                
                # Извлекаем товарную позицию
                item = self._extract_item_from_row(row, column_mapping, table_idx, row_idx)
                
                # Отладка для файла "пример входных данных от поставщиков.pdf"
                if table_idx == 0 and row_idx < 3:  # Первые 3 строки первой таблицы
                    logger.info(f"Отладка строки {row_idx}:")
                    logger.info(f"  Извлеченный элемент: {item}")
                    if item:
                        logger.info(f"  Название: '{item.get('name')}'")
                        logger.info(f"  Количество: {item.get('qty')}")
                        logger.info(f"  Цена: {item.get('price')}")
                        logger.info(f"  Единица: '{item.get('unit')}'")
                        logger.info(f"  Сумма: {item.get('total')}")
                
                if item and self._is_valid_product(item):
                    logger.info(f"Найдена валидная позиция в строке {row_idx}: {item.get('name', 'N/A')}")
                    items.append(item)
                else:
                    logger.debug(f"Строка {row_idx} не содержит валидной позиции")
                    # Подробная отладка для файла "пример входных данных от поставщиков.pdf"
                    if table_idx == 0 and row_idx < 3:  # Первые 3 строки первой таблицы
                        logger.debug(f"Отладка строки {row_idx}:")
                        logger.debug(f"  Извлеченный элемент: {item}")
                        if item:
                            logger.debug(f"  Название: '{item.get('name')}'")
                            logger.debug(f"  Количество: {item.get('qty')}")
                            logger.debug(f"  Цена: {item.get('price')}")
                            logger.debug(f"  Единица: '{item.get('unit')}'")
                    
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
                # Очищаем от переносов строк и лишних символов
                col_str = re.sub(r'\s+', ' ', col_str).strip()
                
                # Номер позиции
                if any(word in col_str for word in ['№', 'номер', 'позиция']):
                    mapping['number'] = i
                
                # Артикул
                elif any(word in col_str for word in ['артикул', 'код', 'арт']):
                    mapping['article'] = i
                
                # Наименование
                elif any(word in col_str for word in ['наименование', 'товары', 'работы', 'услуги', 'название', 'наимен']):
                    mapping['name'] = i
                
                # Количество
                elif any(word in col_str for word in ['количество', 'кол-во', 'колво']):
                    mapping['qty'] = i
                
                # Единица измерения
                elif any(word in col_str for word in ['ед', 'единица', 'изм']):
                    mapping['unit'] = i
                
                # Цена
                elif any(word in col_str for word in ['цена', 'стоимость', 'руб', 'без ндс']):
                    mapping['price'] = i
                
                # Сумма
                elif any(word in col_str for word in ['сумма', 'итого', 'всего', 'с ндс']):
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
        
        if len(columns) >= 13:
            # Структура из "пример входных данных от поставщиков.pdf"
            # ['№', 'Наимен', 'ование', '', '', 'Кол-во', 'Ед. изм.', 'Срок поставки', 'Цена (б', 'ез НДС)', 'Сумма (с НДС)', '_page', '_table_id']
            mapping = {
                'number': 0,
                'name': 1,  # 'Наимен' - первая часть названия
                'qty': 5,   # 'Кол-во'
                'unit': 6,  # 'Ед. изм.'
                'price': 8, # 'Цена (б'
                'total': 10 # 'Сумма (с НДС)'
            }
        elif len(columns) >= 10:
            # Структура с артикулом: №, Артикул, Наименование, Количество, Ед.изм., Цена, Сумма
            mapping = {
                'number': 0,
                'article': 1,
                'name': 2,
                'qty': 3,
                'unit': 4,
                'price': 5,
                'total': 6
            }
        elif len(columns) >= 7:
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
            header_indicators = ['№', 'номер', 'артикул', 'товары', 'количество', 'цена', 'сумма', 'наименование', 'наимен']
            
            # Проверяем только если первая ячейка содержит заголовок
            if any(word in first_cell.lower() for word in header_indicators):
                logger.debug(f"Строка помечена как заголовок: {first_cell}")
                return True
            
            # Проверяем, что первая ячейка не является номером позиции
            if first_cell.strip().isdigit():
                logger.debug(f"Первая ячейка - номер позиции: {first_cell}")
                return False
            
            return False
        except:
            return False
    
    def _is_service_row(self, row: pd.Series) -> bool:
        """Проверяет, является ли строка служебной"""
        try:
            # Проверяем все ячейки в текущей строке
            for cell in row:
                if pd.notna(cell):
                    cell_str = str(cell).lower()
                    
                    # Проверяем служебные слова
                    if any(word in cell_str for word in self.exclude_words):
                        logger.debug(f"Найдено служебное слово в строке: {cell_str}")
                        return True
            
            return False
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
                            # Очищаем от переносов строк
                            item[field] = re.sub(r'\s+', ' ', str(value)).strip()
                    else:
                        item[field] = None
            
            # Специальная обработка для единиц измерения
            if 'unit' in mapping and not item.get('unit'):
                # Ищем единицу измерения в соседних колонках
                unit_col = mapping['unit']
                if unit_col + 1 < len(row) and pd.notna(row.iloc[unit_col + 1]):
                    unit_value = str(row.iloc[unit_col + 1]).strip()
                    if unit_value and unit_value != 'None' and len(unit_value) <= 5:  # Короткие единицы измерения
                        item['unit'] = unit_value
            
            # Специальная обработка для разбитых названий (как в "пример входных данных от поставщиков.pdf")
            if 'name' in mapping and item.get('name'):
                name_col = mapping['name']
                # Если название разбито на несколько колонок, объединяем их
                for i in range(1, 5):  # Проверяем до 4 следующих колонок
                    if name_col + i < len(row) and pd.notna(row.iloc[name_col + i]):
                        next_value = str(row.iloc[name_col + i]).strip()
                        if next_value and next_value != 'None' and len(next_value) > 2:
                            # Очищаем от переносов строк
                            next_value = re.sub(r'\s+', ' ', next_value)
                            item['name'] = item['name'] + ' ' + next_value
            
            logger.debug(f"Извлеченный элемент: {item}")
            
            # Проверяем минимальные требования
            if not item.get('name') or item.get('qty') is None or item.get('price') is None:
                logger.debug(f"Недостаточно данных для элемента: {item}")
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
                logger.debug(f"Недостаточно полей: name={item.get('name')}, qty={item.get('qty')}, price={item.get('price')}")
                return False
            
            # Исключаем служебную информацию
            name = str(item.get('name', '')).lower()
            
            # Проверяем, не содержит ли название служебные слова
            if any(word in name for word in self.exclude_words):
                logger.debug(f"Название содержит служебные слова: {name}")
                return False
            
            # Проверяем, что название содержит буквы
            if not re.search(r'[а-яёa-z]{2,}', name, re.IGNORECASE):
                logger.debug(f"Название не содержит буквы: {name}")
                return False
            
            # Проверяем, что количество и цена положительные
            if item.get('qty', 0) <= 0 or item.get('price', 0) <= 0:
                logger.debug(f"Некорректные значения: qty={item.get('qty')}, price={item.get('price')}")
                return False
            
            # Проверяем, что название не слишком короткое
            if len(name.strip()) < 5:
                logger.debug(f"Название слишком короткое: {name}")
                return False
            
            # Проверяем, что это похоже на товар
            if any(re.search(pattern, name, re.IGNORECASE) for pattern in self.product_patterns):
                logger.debug(f"Найдено совпадение с паттерном товара: {name}")
                return True
            
            # Если не похоже на товар, но содержит технические характеристики
            if re.search(r'\d+[х×]\d+', name) or re.search(r'\d+[кмлшт]', name):
                logger.debug(f"Найдены технические характеристики: {name}")
                return True
            
            logger.debug(f"Не прошло валидацию: {name}")
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
