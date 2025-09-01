"""
Система профилей поставщиков для специализированного парсинга
"""

import re
import logging
from typing import List, Dict, Any, Optional, Callable
import pandas as pd

logger = logging.getLogger(__name__)

class SupplierProfile:
    """Профиль поставщика с правилами парсинга"""
    
    def __init__(self, supplier_id: str, name: str, inn: str = None):
        self.supplier_id = supplier_id
        self.name = name
        self.inn = inn
        self.column_mapping = {}
        self.header_patterns = []
        self.item_patterns = []
        self.filters = []
        self.validators = []
    
    def set_column_mapping(self, mapping: Dict[str, int]):
        """Установка сопоставления колонок"""
        self.column_mapping = mapping
    
    def add_header_pattern(self, pattern: str):
        """Добавление паттерна заголовка"""
        self.header_patterns.append(re.compile(pattern, re.IGNORECASE))
    
    def add_item_pattern(self, pattern: str):
        """Добавление паттерна товарной позиции"""
        self.item_patterns.append(re.compile(pattern, re.IGNORECASE))
    
    def add_filter(self, filter_func: Callable[[Dict[str, Any]], bool]):
        """Добавление фильтра для элементов"""
        self.filters.append(filter_func)
    
    def add_validator(self, validator_func: Callable[[Dict[str, Any]], bool]):
        """Добавление валидатора для элементов"""
        self.validators.append(validator_func)
    
    def parse_document(self, text: str, tables: List[pd.DataFrame]) -> List[Dict[str, Any]]:
        """Парсинг документа с использованием профиля поставщика"""
        items = []
        
        # Парсим таблицы
        if tables:
            table_items = self._parse_tables(tables)
            items.extend(table_items)
        
        # Парсим текст
        if text:
            text_items = self._parse_text(text)
            items.extend(text_items)
        
        # Применяем фильтры и валидаторы
        filtered_items = []
        for item in items:
            # Применяем фильтры
            if all(filter_func(item) for filter_func in self.filters):
                # Применяем валидаторы
                if all(validator_func(item) for validator_func in self.validators):
                    item['supplier'] = self.name
                    item['supplier_id'] = self.supplier_id
                    item['confidence'] = min(item.get('confidence', 0.8) + 0.1, 1.0)  # Повышаем уверенность
                    filtered_items.append(item)
        
        return filtered_items
    
    def _parse_tables(self, tables: List[pd.DataFrame]) -> List[Dict[str, Any]]:
        """Парсинг таблиц с использованием профиля"""
        items = []
        
        for table_idx, table in enumerate(tables):
            try:
                # Проверяем, подходит ли таблица для этого профиля
                if self._is_compatible_table(table):
                    table_items = self._parse_table_with_profile(table, table_idx)
                    items.extend(table_items)
                    
            except Exception as e:
                logger.warning(f"Ошибка парсинга таблицы {table_idx} для поставщика {self.name}: {e}")
                continue
        
        return items
    
    def _is_compatible_table(self, table: pd.DataFrame) -> bool:
        """Проверка совместимости таблицы с профилем"""
        if not self.header_patterns:
            return True
        
        # Проверяем заголовки таблицы
        headers_text = ' '.join([str(col) for col in table.columns if pd.notna(col) and str(col).strip()])
        
        for pattern in self.header_patterns:
            if pattern.search(headers_text):
                return True
        
        return False
    
    def _parse_table_with_profile(self, table: pd.DataFrame, table_idx: int) -> List[Dict[str, Any]]:
        """Парсинг таблицы с использованием профиля"""
        items = []
        
        for row_idx, row in table.iterrows():
            try:
                # Пропускаем заголовки
                if self._is_header_row(row):
                    continue
                
                # Парсим строку с использованием профиля
                item = self._parse_row_with_profile(row, table_idx, row_idx)
                if item:
                    items.append(item)
                    
            except Exception as e:
                logger.debug(f"Ошибка парсинга строки {row_idx}: {e}")
                continue
        
        return items
    
    def _is_header_row(self, row: pd.Series) -> bool:
        """Проверка, является ли строка заголовком"""
        first_cell = str(row.iloc[0]) if len(row) > 0 else ''
        header_indicators = ['№', 'номер', 'артикул', 'товары', 'количество', 'цена', 'сумма', 'наименование']
        return any(word in first_cell.lower() for word in header_indicators)
    
    def _parse_row_with_profile(self, row: pd.Series, table_idx: int, row_idx: int) -> Optional[Dict[str, Any]]:
        """Парсинг строки с использованием профиля"""
        try:
            # Получаем значения из колонок согласно профилю
            item = {}
            
            for field, col_idx in self.column_mapping.items():
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
            item['source'] = f'profile_{self.supplier_id}_table_{table_idx}_row_{row_idx}'
            item['confidence'] = 0.95
            
            # Вычисляем общую сумму если не указана
            if item.get('total') is None and item.get('qty') and item.get('price'):
                item['total'] = item['qty'] * item['price']
            
            return item
            
        except Exception as e:
            logger.debug(f"Ошибка парсинга строки с профилем: {e}")
            return None
    
    def _parse_text(self, text: str) -> List[Dict[str, Any]]:
        """Парсинг текста с использованием профиля"""
        items = []
        lines = text.split('\n')
        
        for line_idx, line in enumerate(lines):
            line = line.strip()
            if not line or len(line) < 10:
                continue
            
            # Пропускаем заголовки и служебные строки
            if self._is_header_line(line) or self._is_service_line(line):
                continue
            
            # Парсим строку с использованием паттернов профиля
            item = self._parse_line_with_profile(line, line_idx)
            if item:
                items.append(item)
        
        return items
    
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
    
    def _parse_line_with_profile(self, line: str, line_idx: int) -> Optional[Dict[str, Any]]:
        """Парсинг строки с использованием паттернов профиля"""
        for pattern in self.item_patterns:
            match = pattern.search(line)
            if match:
                try:
                    item = {}
                    for group_name, value in match.groupdict().items():
                        if group_name in ['qty', 'price', 'total']:
                            item[group_name] = self._parse_number(value)
                        else:
                            item[group_name] = value.strip() if value else ''
                    
                    # Проверяем минимальные требования
                    if not item.get('name') or item.get('qty') is None or item.get('price') is None:
                        continue
                    
                    # Добавляем стандартные поля
                    item['currency'] = 'RUB'
                    item['source'] = f'profile_{self.supplier_id}_text_line_{line_idx}'
                    item['confidence'] = 0.9
                    
                    # Вычисляем общую сумму если не указана
                    if item.get('total') is None and item.get('qty') and item.get('price'):
                        item['total'] = item['qty'] * item['price']
                    
                    return item
                    
                except Exception as e:
                    logger.debug(f"Ошибка парсинга строки с паттерном: {e}")
                    continue
        
        return None
    
    def _parse_number(self, value: Any) -> Optional[float]:
        """Парсинг чисел с поддержкой русских форматов"""
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


class SupplierProfileManager:
    """Менеджер профилей поставщиков"""
    
    def __init__(self):
        self.profiles = {}
        self._load_default_profiles()
    
    def _load_default_profiles(self):
        """Загрузка профилей по умолчанию"""
        
        # Профиль для ООО "БАЛТКАБЕЛЬ"
        baltkabel_profile = SupplierProfile(
            supplier_id="baltkabel",
            name="ООО 'БАЛТКАБЕЛЬ'",
            inn="7800000000"  # Примерный ИНН
        )
        
        # Настройка для коммерческих предложений БАЛТКАБЕЛЬ
        baltkabel_profile.set_column_mapping({
            'number': 0,
            'name': 1,
            'qty': 2,
            'unit': 3,
            'price': 5,
            'total': 6
        })
        
        # Добавляем паттерны заголовков
        baltkabel_profile.add_header_pattern(r'наименование.*кол-во.*цена')
        baltkabel_profile.add_header_pattern(r'товары.*количество.*стоимость')
        
        # Добавляем фильтры
        baltkabel_profile.add_filter(lambda item: 'СИП' in item.get('name', ''))
        baltkabel_profile.add_filter(lambda item: item.get('qty', 0) > 0)
        
        # Добавляем валидаторы
        baltkabel_profile.add_validator(lambda item: len(item.get('name', '')) > 5)
        baltkabel_profile.add_validator(lambda item: item.get('price', 0) > 0)
        
        self.profiles['baltkabel'] = baltkabel_profile
        
        # Профиль для ООО "Энергофорсаж"
        energoforsazh_profile = SupplierProfile(
            supplier_id="energoforsazh",
            name="ООО 'Энергофорсаж'",
            inn="5027177653"
        )
        
        # Настройка для счетов Энергофорсаж
        energoforsazh_profile.set_column_mapping({
            'number': 0,
            'article': 1,
            'name': 2,
            'qty': 3,
            'unit': 4,
            'price': 5,
            'total': 6
        })
        
        # Добавляем паттерны заголовков
        energoforsazh_profile.add_header_pattern(r'№.*артикул.*товары.*количество')
        energoforsazh_profile.add_header_pattern(r'номер.*код.*наименование.*кол-во')
        
        # Добавляем фильтры
        energoforsazh_profile.add_filter(lambda item: 'кабель' in item.get('name', '').lower())
        energoforsazh_profile.add_filter(lambda item: item.get('qty', 0) > 0)
        
        # Добавляем валидаторы
        energoforsazh_profile.add_validator(lambda item: len(item.get('name', '')) > 5)
        energoforsazh_profile.add_validator(lambda item: item.get('price', 0) > 0)
        
        self.profiles['energoforsazh'] = energoforsazh_profile
        
        # Профиль для ООО "Элком-Электро"
        elkom_profile = SupplierProfile(
            supplier_id="elkom",
            name="ООО 'Элком-Электро'",
            inn="7703214111"
        )
        
        # Настройка для счетов Элком-Электро
        elkom_profile.set_column_mapping({
            'number': 0,
            'name': 1,
            'qty': 2,
            'unit': 3,
            'price': 4,
            'total': 5
        })
        
        # Добавляем паттерны заголовков
        elkom_profile.add_header_pattern(r'наименование.*количество.*цена')
        elkom_profile.add_header_pattern(r'товары.*кол-во.*стоимость')
        
        # Добавляем фильтры
        elkom_profile.add_filter(lambda item: 'кабель' in item.get('name', '').lower())
        elkom_profile.add_filter(lambda item: item.get('qty', 0) > 0)
        
        # Добавляем валидаторы
        elkom_profile.add_validator(lambda item: len(item.get('name', '')) > 5)
        elkom_profile.add_validator(lambda item: item.get('price', 0) > 0)
        
        self.profiles['elkom'] = elkom_profile
        
        # Профиль для ООО "СТАРТ"
        start_profile = SupplierProfile(
            supplier_id="start",
            name="ООО 'СТАРТ'",
            inn="2308266335"
        )
        
        # Настройка для счетов СТАРТ
        start_profile.set_column_mapping({
            'number': 0,
            'name': 1,
            'qty': 2,
            'unit': 3,
            'price': 4,
            'total': 5
        })
        
        # Добавляем паттерны заголовков
        start_profile.add_header_pattern(r'наименование.*количество.*цена')
        start_profile.add_header_pattern(r'товары.*кол-во.*стоимость')
        
        # Добавляем фильтры
        start_profile.add_filter(lambda item: item.get('qty', 0) > 0)
        start_profile.add_filter(lambda item: not any(word in item.get('name', '').lower() for word in ['инн', 'кпп', 'счет', 'банк']))
        
        # Добавляем валидаторы
        start_profile.add_validator(lambda item: len(item.get('name', '')) > 5)
        start_profile.add_validator(lambda item: item.get('price', 0) > 0)
        
        self.profiles['start'] = start_profile
    
    def identify_supplier(self, text: str, tables: List[pd.DataFrame] = None) -> Optional[str]:
        """Определение поставщика по содержимому документа"""
        text_lower = text.lower()
        
        # Ищем по названию компании
        if 'балткабель' in text_lower:
            return 'baltkabel'
        elif 'энергофорсаж' in text_lower:
            return 'energoforsazh'
        elif 'элком-электро' in text_lower or 'элком' in text_lower:
            return 'elkom'
        elif 'старт' in text_lower:
            return 'start'
        
        # Ищем по ИНН
        inn_patterns = [
            r'инн\s*(\d{10,12})',
            r'идентификационный номер налогоплательщика\s*(\d{10,12})'
        ]
        
        for pattern in inn_patterns:
            match = re.search(pattern, text_lower)
            if match:
                inn = match.group(1)
                # Сопоставляем ИНН с профилями
                for profile_id, profile in self.profiles.items():
                    if profile.inn and profile.inn in inn:
                        return profile_id
        
        return None
    
    def get_profile(self, supplier_id: str) -> Optional[SupplierProfile]:
        """Получение профиля поставщика"""
        return self.profiles.get(supplier_id)
    
    def add_profile(self, supplier_id: str, profile: SupplierProfile):
        """Добавление нового профиля"""
        self.profiles[supplier_id] = profile
    
    def list_profiles(self) -> List[str]:
        """Список всех профилей"""
        return list(self.profiles.keys())
    
    def parse_with_profile(self, text: str, tables: List[pd.DataFrame] = None) -> Dict[str, Any]:
        """Парсинг с автоматическим определением профиля"""
        # Определяем поставщика
        supplier_id = self.identify_supplier(text, tables)
        
        if supplier_id:
            profile = self.get_profile(supplier_id)
            if profile:
                items = profile.parse_document(text, tables)
                return {
                    'supplier_id': supplier_id,
                    'supplier_name': profile.name,
                    'items': items,
                    'count': len(items),
                    'total_cost': sum(item.get('total', 0) for item in items),
                    'avg_confidence': sum(item.get('confidence', 0) for item in items) / len(items) if items else 0,
                    'method': 'supplier_profile'
                }
        
        return {
            'supplier_id': None,
            'supplier_name': None,
            'items': [],
            'count': 0,
            'total_cost': 0,
            'avg_confidence': 0,
            'method': 'no_profile'
        }
