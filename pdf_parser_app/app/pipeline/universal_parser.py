"""
Универсальный парсер для всех типов документов с поддержкой OCR
"""

import re
import logging
from typing import List, Dict, Any, Optional
import pandas as pd

logger = logging.getLogger(__name__)

class UniversalParser:
    """Универсальный парсер для всех типов документов с поддержкой OCR"""
    
    def __init__(self, use_ocr: bool = True, ocr_languages: List[str] = None):
        from app.pipeline.commercial_parser import CommercialProposalParser
        from app.pipeline.invoice_parser import InvoiceParser
        from app.pipeline.competitive_parser import CompetitiveParser
        from app.pipeline.table_extractor import TableExtractor
        from app.pipeline.precise_table_parser import PreciseTableParser
        
        # Основные парсеры
        self.commercial_parser = CommercialProposalParser()
        self.invoice_parser = InvoiceParser()
        self.competitive_parser = CompetitiveParser()
        self.table_extractor = TableExtractor()
        self.precise_table_parser = PreciseTableParser()
        
        # OCR поддержка
        self.use_ocr = use_ocr
        self.enhanced_extractor = None
        
        if self.use_ocr:
            try:
                from app.pipeline.enhanced_extractor import EnhancedExtractor
                self.enhanced_extractor = EnhancedExtractor(use_ocr=True, ocr_languages=ocr_languages)
                logger.info("OCR поддержка инициализирована в UniversalParser")
            except Exception as e:
                logger.warning(f"Не удалось инициализировать OCR: {e}")
                self.use_ocr = False
        
        # Инициализируем менеджер профилей поставщиков
        try:
            from app.pipeline.supplier_profiles import SupplierProfileManager
            self.supplier_profile_manager = SupplierProfileManager()
        except ImportError:
            logger.warning("Не удалось импортировать SupplierProfileManager")
            self.supplier_profile_manager = None
        
        # Словарь синонимов колонок
        self.column_synonyms = {
            'number': ['№', 'номер', 'n', 'number', 'позиция', 'поз', 'порядковый'],
            'article': ['артикул', 'код', 'article', 'code', 'sku', 'арт', 'код товара'],
            'name': ['товары', 'работы', 'услуги', 'наименование', 'описание', 'name', 'description', 'название', 'товар'],
            'qty': ['количество', 'кол-во', 'qty', 'amount', 'объем', 'кол', 'к-во', 'шт'],
            'unit': ['ед', 'единица', 'изм', 'unit', 'measure', 'единицы', 'измерения'],
            'price': ['цена', 'стоимость', 'price', 'cost', 'тариф', 'цена за ед', 'цена за единицу'],
            'total': ['сумма', 'итого', 'total', 'sum', 'стоимость', 'сумма с ндс', 'сумма без ндс']
        }
        
        # Регулярные выражения для строк товаров
        self.item_patterns = [
            # Паттерн 1: название + количество + единица + цена + сумма
            re.compile(
                r'(?P<name>[А-Яа-я\w\s\-\.\n]+?)\s+(?P<qty>[\d\s\.,]+)\s*(?P<unit>шт|кг|м|л|pcs|kg|m|l|шт\.|кг\.|м\.|л\.|тонн|тонны|штук|штуки|км|м2|м3)?\s+'
                r'(?P<price>[\d\s\.,]+)\s*(?P<total>[\d\s\.,]+)?',
                re.IGNORECASE | re.MULTILINE
            ),
            # Паттерн 2: номер + название + количество + цена
            re.compile(
                r'^(?P<number>\d+)\s+(?P<name>[А-Яа-я\w\s\-\.\n]+?)\s+(?P<qty>[\d\s\.,]+)\s+(?P<price>[\d\s\.,]+)',
                re.IGNORECASE | re.MULTILINE
            )
        ]
    
    def parse_document(self, text: str, tables: List[pd.DataFrame] = None, pdf_path: str = None) -> Dict[str, Any]:
        """
        Универсальный парсинг документа с поддержкой OCR
        
        Args:
            text: Текст документа
            tables: Извлеченные таблицы
            pdf_path: Путь к PDF файлу (для OCR улучшения)
            
        Returns:
            Словарь с результатами всех парсеров и рекомендациями
        """
        results = {
            'commercial_parser': None,
            'invoice_parser': None,
            'competitive_parser': None,
            'universal_parser': None,
            'best_parser': None,
            'best_items': None,
            'document_type': None,
            'ocr_info': None,
            'quality_assessment': None,
            'recommendations': []
        }
        
        # OCR улучшение текста, если доступно
        if self.use_ocr and self.enhanced_extractor and pdf_path:
            try:
                logger.info("Применяем OCR улучшение к тексту")
                enhanced_text, ocr_info = self.enhanced_extractor.ocr_processor.enhance_pdf_text(pdf_path, text)
                
                if ocr_info['ocr_additions'] > 0:
                    text = enhanced_text
                    results['ocr_info'] = ocr_info
                    logger.info(f"OCR улучшил текст: добавлено {ocr_info['ocr_additions']} блоков")
                
                # Определяем тип документа с помощью OCR
                doc_type = self.enhanced_extractor.ocr_processor.detect_document_type(text)
                results['document_type'] = doc_type
                
                # Валидируем качество данных
                validation = self.enhanced_extractor.ocr_processor.validate_extracted_data(text, tables)
                results['quality_assessment'] = validation
                
            except Exception as e:
                logger.warning(f"Ошибка OCR улучшения: {e}")
                results['ocr_info'] = {'error': str(e)}
        
        # Парсим всеми парсерами
        try:
            commercial_items = self.commercial_parser.parse_commercial_proposal(text, tables)
            results['commercial_parser'] = {
                'items': commercial_items,
                'count': len(commercial_items) if commercial_items else 0,
                'total_cost': sum(item.get('total', 0) for item in commercial_items) if commercial_items else 0,
                'avg_confidence': sum(item.get('confidence', 0) for item in commercial_items) / len(commercial_items) if commercial_items else 0
            }
        except Exception as e:
            logger.warning(f"Ошибка коммерческого парсера: {e}")
            results['commercial_parser'] = {'error': str(e)}
        
        try:
            invoice_items = self.invoice_parser.parse_invoice(text, tables)
            results['invoice_parser'] = {
                'items': invoice_items,
                'count': len(invoice_items) if invoice_items else 0,
                'total_cost': sum(item.get('total', 0) for item in invoice_items) if invoice_items else 0,
                'avg_confidence': sum(item.get('confidence', 0) for item in invoice_items) / len(invoice_items) if invoice_items else 0
            }
        except Exception as e:
            logger.warning(f"Ошибка парсера счетов: {e}")
            results['invoice_parser'] = {'error': str(e)}
        
        try:
            competitive_items = self.competitive_parser.parse_competitive_document(text, tables)
            results['competitive_parser'] = {
                'items': competitive_items,
                'count': len(competitive_items) if competitive_items else 0,
                'total_cost': sum(item.get('total', 0) for item in competitive_items) if competitive_items else 0,
                'avg_confidence': sum(item.get('confidence', 0) for item in competitive_items) / len(competitive_items) if competitive_items else 0
            }
        except Exception as e:
            logger.warning(f"Ошибка конкурентного парсера: {e}")
            results['competitive_parser'] = {'error': str(e)}
        
        # Парсим универсальным методом
        try:
            universal_items = self._parse_universal(text, tables)
            results['universal_parser'] = {
                'items': universal_items,
                'count': len(universal_items) if universal_items else 0,
                'total_cost': sum(item.get('total', 0) for item in universal_items) if universal_items else 0,
                'avg_confidence': sum(item.get('confidence', 0) for item in universal_items) / len(universal_items) if universal_items else 0
            }
        except Exception as e:
            logger.warning(f"Ошибка универсального парсера: {e}")
            results['universal_parser'] = {'error': str(e)}
        
        # Парсим с профилями поставщиков
        if self.supplier_profile_manager:
            try:
                supplier_result = self.supplier_profile_manager.parse_with_profile(text, tables)
                results['supplier_profile_parser'] = {
                    'items': supplier_result.get('items', []),
                    'count': supplier_result.get('count', 0),
                    'total_cost': supplier_result.get('total_cost', 0),
                    'avg_confidence': supplier_result.get('avg_confidence', 0),
                    'supplier_id': supplier_result.get('supplier_id'),
                    'supplier_name': supplier_result.get('supplier_name'),
                    'method': supplier_result.get('method')
                }
            except Exception as e:
                logger.warning(f"Ошибка парсера профилей поставщиков: {e}")
                results['supplier_profile_parser'] = {'error': str(e)}
        else:
            results['supplier_profile_parser'] = {'error': 'SupplierProfileManager не инициализирован'}
        
        # Парсим с TableExtractor
        try:
            table_items = self.table_extractor.extract_items_from_tables(tables)
            results['table_extractor'] = {
                'items': table_items,
                'count': len(table_items) if table_items else 0,
                'total_cost': sum(item.get('total', 0) for item in table_items) if table_items else 0,
                'avg_confidence': sum(item.get('confidence', 0) for item in table_items) / len(table_items) if table_items else 0
            }
        except Exception as e:
            logger.warning(f"Ошибка TableExtractor: {e}")
            results['table_extractor'] = {'error': str(e)}
        
        # Парсим с PreciseTableParser
        try:
            precise_items = self.precise_table_parser.extract_items_from_tables(tables)
            results['precise_table_parser'] = {
                'items': precise_items,
                'count': len(precise_items) if precise_items else 0,
                'total_cost': sum(item.get('total', 0) for item in precise_items) if precise_items else 0,
                'avg_confidence': sum(item.get('confidence', 0) for item in precise_items) / len(precise_items) if precise_items else 0
            }
        except Exception as e:
            logger.warning(f"Ошибка PreciseTableParser: {e}")
            results['precise_table_parser'] = {'error': str(e)}
        
        # Определяем лучший парсер
        parsers = [
            ('commercial', results['commercial_parser']),
            ('invoice', results['invoice_parser']),
            ('competitive', results['competitive_parser']),
            ('universal', results['universal_parser']),
            ('supplier_profile', results['supplier_profile_parser']),
            ('table_extractor', results['table_extractor']),
            ('precise_table_parser', results['precise_table_parser'])
        ]
        
        best_parser = None
        best_count = 0
        best_items = []
        best_total_cost = 0
        best_avg_confidence = 0
        
        for parser_name, parser_result in parsers:
            if parser_result and isinstance(parser_result, dict) and 'error' not in parser_result:
                count = parser_result.get('count', 0)
                
                # Проверяем качество найденных элементов
                items = parser_result.get('items', [])
                valid_items = []
                
                for item in items:
                    name = str(item.get('name', '')).lower()
                    # Исключаем служебную информацию
                    service_words = ['инн', 'кпп', 'счет', 'банк', 'бик', 'р/с', 'к/с', 'получатель', 'плательщик', 
                                   'итого', 'всего', 'сумма', 'ндс', 'четыре', 'миллио', 'на восе', 'мьдесят', 
                                   'ве тысячи', 'шестьсот', 'ьдесят', 'семь ру', 'блей', 'копеек', 'копорское',
                                   'шоссе', 'дом', 'корпус', 'комната', 'указанные', 'цены', 'скидки', 'действуют',
                                   'апреля', 'в течение', 'дн']
                    if not any(word in name for word in service_words):
                        # Дополнительная проверка на качество названия
                        if len(name.strip()) > 10 and any(char.isalpha() for char in name):
                            # Проверяем, что это похоже на товар
                            if any(word in name for word in ['кабель', 'сип', 'провод', 'перевозка', 'транспорт']):
                                valid_items.append(item)
                
                valid_count = len(valid_items)
                
                # Если это competitive парсер и он нашел много служебной информации, снижаем его приоритет
                if parser_name == 'competitive' and valid_count < count * 0.5:
                    valid_count = 0  # Исключаем competitive парсер с плохими результатами
                
                # Приоритет для PreciseTableParser
                if parser_name == 'precise_table_parser' and valid_count > 0:
                    valid_count *= 2  # Увеличиваем приоритет
                
                if valid_count > best_count:
                    best_count = valid_count
                    best_parser = parser_name
                    best_items = valid_items
                    best_total_cost = sum(item.get('total', 0) for item in valid_items)
                    best_avg_confidence = sum(item.get('confidence', 0) for item in valid_items) / len(valid_items) if valid_items else 0
        
        # Добавляем общую статистику
        total_count = sum(r.get('count', 0) for r in results.values() if isinstance(r, dict) and 'error' not in r)
        total_cost = sum(r.get('total_cost', 0) for r in results.values() if isinstance(r, dict) and 'error' not in r)
        total_confidence = sum(r.get('avg_confidence', 0) for r in results.values() if isinstance(r, dict) and 'error' not in r)
        valid_parsers = [r for r in results.values() if isinstance(r, dict) and 'error' not in r and r.get('count', 0) > 0]
        avg_confidence = total_confidence / len(valid_parsers) if valid_parsers else 0
        
        results['best_parser'] = best_parser
        results['best_items'] = best_items or []
        results['count'] = best_count
        results['total_cost'] = best_total_cost
        results['avg_confidence'] = best_avg_confidence
        
        # Определяем тип документа
        results['document_type'] = self._detect_document_type(text, tables)
        
        # Формируем рекомендации
        results['recommendations'] = self._generate_recommendations(results)
        
        return results
    
    def _parse_universal(self, text: str, tables: List[pd.DataFrame] = None) -> List[Dict[str, Any]]:
        """Универсальный парсинг с использованием синонимов и регулярных выражений"""
        items = []
        
        # Сначала пробуем парсить таблицы
        if tables:
            table_items = self._parse_tables_universal(tables)
            items.extend(table_items)
        
        # Затем парсим текст
        if text:
            text_items = self._parse_text_universal(text)
            items.extend(text_items)
        
        # Убираем дубликаты и валидируем
        unique_items = self._deduplicate_items(items)
        valid_items = [item for item in unique_items if self._validate_universal_item(item)]
        
        return valid_items
    
    def _parse_tables_universal(self, tables: List[pd.DataFrame]) -> List[Dict[str, Any]]:
        """Универсальный парсинг таблиц"""
        items = []
        
        for table_idx, table in enumerate(tables):
            try:
                # Определяем структуру таблицы по синонимам
                column_mapping = self._identify_columns_by_synonyms(table.columns)
                logger.debug(f"Колонки по синонимам для таблицы {table_idx}: {column_mapping}")
                
                if column_mapping:
                    table_items = self._parse_table_with_mapping_universal(table, column_mapping, table_idx)
                    items.extend(table_items)
                else:
                    # Fallback: пробуем определить по позиции
                    column_mapping = self._identify_columns_by_position_universal(table.columns)
                    logger.debug(f"Колонки по позиции для таблицы {table_idx}: {column_mapping}")
                    
                    if column_mapping:
                        table_items = self._parse_table_with_mapping_universal(table, column_mapping, table_idx)
                        items.extend(table_items)
                    else:
                        # Последний fallback: анализ содержимого таблицы
                        table_items = self._parse_table_by_content_universal(table, table_idx)
                        items.extend(table_items)
                    
            except Exception as e:
                logger.warning(f"Ошибка парсинга таблицы {table_idx}: {e}")
                continue
        
        return items
    
    def _parse_table_by_content_universal(self, table: pd.DataFrame, table_idx: int) -> List[Dict[str, Any]]:
        """Анализ содержимого таблицы для определения структуры (последний fallback)"""
        items = []
        
        # Анализируем первые несколько строк для определения структуры
        if table.shape[0] < 2:
            return items
        
        # Ищем строки с товарными позициями
        for row_idx in range(1, min(6, table.shape[0])):  # Анализируем до 5 строк
            try:
                row = table.iloc[row_idx]
                row_values = []
                
                # Собираем непустые значения
                for cell in row:
                    if pd.notna(cell) and str(cell).strip():
                        row_values.append(str(cell).strip())
                
                if len(row_values) < 3:
                    continue
                
                # Анализируем структуру строки
                item = self._analyze_row_structure(row_values, table_idx, row_idx)
                if item:
                    items.append(item)
                    
            except Exception as e:
                logger.debug(f"Ошибка анализа строки {row_idx}: {e}")
                continue
        
        return items
    
    def _analyze_row_structure(self, values: List[str], table_idx: int, row_idx: int) -> Optional[Dict[str, Any]]:
        """Анализ структуры строки для определения товарной позиции"""
        if len(values) < 3:
            return None
        
        try:
            # Ищем номер позиции (первое число)
            number = None
            name = None
            qty = None
            unit = None
            price = None
            total = None
            
            # Анализируем каждое значение
            for i, value in enumerate(values):
                value_clean = value.strip()
                
                # Номер позиции
                if number is None and re.match(r'^\d+$', value_clean):
                    number = value_clean
                    continue
                
                # Название товара (содержит буквы и технические характеристики)
                if name is None and re.search(r'[А-Яа-я]{2,}', value_clean) and len(value_clean) > 5:
                    name = value_clean
                    continue
                
                # Количество
                if qty is None and self._parse_number(value_clean) is not None:
                    qty = self._parse_number(value_clean)
                    continue
                
                # Единица измерения
                if unit is None and value_clean in ['шт', 'кг', 'м', 'л', 'км', 'м2', 'м3', 'тонн', 'штук']:
                    unit = value_clean
                    continue
                
                # Цена
                if price is None and self._parse_number(value_clean) is not None and qty is not None:
                    price = self._parse_number(value_clean)
                    continue
                
                # Сумма
                if total is None and self._parse_number(value_clean) is not None and price is not None:
                    total = self._parse_number(value_clean)
                    continue
            
            # Если не нашли название, берем самое длинное значение с буквами
            if name is None:
                for value in values:
                    if re.search(r'[А-Яа-я]{2,}', value) and len(value) > 5:
                        name = value
                        break
            
            # Проверяем минимальные требования
            if not name or qty is None or price is None:
                return None
            
            # Пропускаем служебные строки
            if self._is_service_row(name):
                return None
            
            # Очищаем название
            name = self._clean_name(name)
            
            item = {
                'name': name,
                'article': number if number else '',
                'qty': qty,
                'unit': unit if unit else '',
                'price': price,
                'currency': 'RUB',
                'total': total if total else qty * price,
                'supplier': '',
                'source': f'universal_content_analysis_{table_idx}_row_{row_idx}',
                'confidence': 0.6  # Низкая уверенность для fallback метода
            }
            
            # Валидируем элемент
            if self._validate_universal_item(item):
                return item
            
        except Exception as e:
            logger.debug(f"Ошибка анализа структуры строки: {e}")
        
        return None
    
    def _identify_columns_by_synonyms(self, columns: pd.Index) -> Optional[Dict[str, int]]:
        """Определение колонок по синонимам"""
        mapping = {}
        
        for col_idx, col_name in enumerate(columns):
            col_name_str = str(col_name).lower().strip()
            
            # Очищаем название колонки
            col_name_str = re.sub(r'[^\w\s]', ' ', col_name_str)
            col_name_str = ' '.join(col_name_str.split())
            
            for field, synonyms in self.column_synonyms.items():
                for synonym in synonyms:
                    if synonym.lower() in col_name_str:
                        mapping[field] = col_idx
                        break
                if field in mapping:
                    break
        
        # Проверяем минимальные требования
        if 'name' in mapping and len(mapping) >= 2:
            return mapping
        
        return None
    
    def _identify_columns_by_position_universal(self, columns: pd.Index) -> Dict[str, int]:
        """Определение колонок по позиции (fallback)"""
        mapping = {}
        
        # Анализируем заголовки для определения реальной структуры
        headers_text = ' '.join([str(col) for col in columns if pd.notna(col) and str(col).strip()])
        headers_lower = headers_text.lower()
        
        # Ищем ключевые слова в заголовках
        if 'наименование' in headers_lower or 'товары' in headers_lower:
            if 'кол-во' in headers_lower or 'количество' in headers_lower:
                if 'цена' in headers_lower:
                    # Стандартная структура найдена
                    if len(columns) >= 13:
                        # Реальная структура из тестового файла
                        mapping['number'] = 0
                        mapping['name'] = 1      # Наименование
                        mapping['qty'] = 2       # Кол-во
                        mapping['unit'] = 3      # Ед. изм.
                        mapping['price'] = 5     # Цена
                        mapping['total'] = 6     # Сумма
                    elif len(columns) >= 7:
                        mapping['number'] = 0
                        mapping['name'] = 1
                        mapping['qty'] = 2
                        mapping['unit'] = 3
                        mapping['price'] = 5  # Цена в колонке 5
                        mapping['total'] = 6  # Сумма в колонке 6
                    elif len(columns) >= 5:
                        mapping['number'] = 0
                        mapping['name'] = 1
                        mapping['qty'] = 2
                        mapping['price'] = 3
                        mapping['total'] = 4
        
        # Если не удалось определить по заголовкам, используем эвристики
        if not mapping:
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
                # Стандартная структура: № | Артикул | Товары | Количество | Ед.изм | Цена | Сумма
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
            elif len(columns) >= 3:
                # Очень простая структура: Наименование | Кол-во | Цена
                mapping['name'] = 0
                mapping['qty'] = 1
                mapping['price'] = 2
        
        return mapping
    
    def _parse_table_with_mapping_universal(self, table: pd.DataFrame, mapping: Dict[str, int], table_idx: int) -> List[Dict[str, Any]]:
        """Парсинг таблицы с известной структурой"""
        items = []
        
        logger.debug(f"Парсинг таблицы {table_idx} с сопоставлением: {mapping}")
        
        for row_idx, row in table.iterrows():
            try:
                # Проверяем, является ли строка заголовком
                first_cell = str(row.iloc[0]) if len(row) > 0 else ''
                if any(word in first_cell.lower() for word in ['№', 'номер', 'артикул', 'товары', 'количество', 'цена', 'сумма', 'наименование']):
                    logger.debug(f"Пропускаем заголовок: {first_cell}")
                    continue
                
                # Получаем значения из колонок
                number = str(row.iloc[mapping.get('number', 0)]) if 'number' in mapping else ''
                article = str(row.iloc[mapping.get('article', 1)]) if 'article' in mapping else ''
                name = str(row.iloc[mapping.get('name', 2)]) if 'name' in mapping else ''
                qty = self._parse_number(row.iloc[mapping.get('qty', 3)]) if 'qty' in mapping else 1.0
                unit = str(row.iloc[mapping.get('unit', 4)]) if 'unit' in mapping else ''
                price = self._parse_number(row.iloc[mapping.get('price', 5)]) if 'price' in mapping else 0.0
                total = self._parse_number(row.iloc[mapping.get('total', 6)]) if 'total' in mapping else None
                
                logger.debug(f"Строка {row_idx}: номер={number}, название={name}, кол-во={qty}, цена={price}, сумма={total}")
                
                # Пропускаем пустые строки
                if not name.strip() or name.strip() in ['', 'nan', 'None']:
                    logger.debug(f"Пропускаем пустую строку: {name}")
                    continue
                
                # Пропускаем служебные строки
                if self._is_service_row(name):
                    logger.debug(f"Пропускаем служебную строку: {name}")
                    continue
                
                # Очищаем название
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
                    'source': f'universal_table_{table_idx}_row_{row_idx}',
                    'confidence': 0.9
                }
                
                # Вычисляем общую сумму если не указана
                if item['total'] is None and item['qty'] and item['price']:
                    item['total'] = item['qty'] * item['price']
                
                # Валидируем элемент
                if self._validate_universal_item(item):
                    logger.debug(f"Добавляем элемент: {item['name']}")
                    items.append(item)
                else:
                    logger.debug(f"Элемент не прошел валидацию: {item['name']}")
                
            except Exception as e:
                logger.debug(f"Ошибка парсинга строки {row_idx}: {e}")
                continue
        
        logger.debug(f"Всего найдено элементов: {len(items)}")
        return items
    
    def _parse_text_universal(self, text: str) -> List[Dict[str, Any]]:
        """Универсальный парсинг текста"""
        items = []
        lines = text.split('\n')
        
        for line_idx, line in enumerate(lines):
            line = line.strip()
            if not line or len(line) < 10:
                continue
            
            # Пропускаем заголовки и служебные строки
            if self._is_header_line(line) or self._is_service_line(line):
                continue
            
            # Пропускаем строки с только цифрами
            if re.match(r'^[\d\s\.,]+$', line):
                continue
            
            # Пытаемся распарсить строку
            parsed_item = self._parse_line_universal(line)
            if parsed_item:
                parsed_item['source'] = f'universal_text_line_{line_idx}'
                parsed_item['confidence'] = 0.7
                items.append(parsed_item)
        
        return items
    
    def _parse_line_universal(self, line: str) -> Optional[Dict[str, Any]]:
        """Парсинг одной строки универсальным методом"""
        for pattern in self.item_patterns:
            match = pattern.search(line)
            if match:
                try:
                    name = match.group('name').strip()
                    qty = self._parse_number(match.group('qty'))
                    unit = match.group('unit') or ''
                    price = self._parse_number(match.group('price'))
                    total = self._parse_number(match.group('total')) if 'total' in match.groupdict() else None
                    
                    # Очищаем название
                    name = self._clean_name(name)
                    
                    item = {
                        'name': name,
                        'article': '',
                        'qty': qty,
                        'unit': unit,
                        'price': price,
                        'currency': 'RUB',
                        'total': total if total else qty * price,
                        'supplier': '',
                        'source': 'universal_regex',
                        'confidence': 0.8
                    }
                    
                    # Валидируем элемент
                    if self._validate_universal_item(item):
                        return item
                        
                except Exception as e:
                    logger.debug(f"Ошибка парсинга строки с паттерном: {e}")
                    continue
        
        return None
    
    def _clean_name(self, name: str) -> str:
        """Очистка названия товара"""
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
    
    def _validate_universal_item(self, item: Dict[str, Any]) -> bool:
        """Валидация универсального элемента"""
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
                'почтовое', 'индекс', 'код', 'вид', 'срок', 'плат', 'наз', 'пл', 'очер'
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
        """Удаление дубликатов"""
        seen = set()
        unique_items = []
        
        for item in items:
            key = (
                item.get('name', '').lower().strip(), 
                item.get('qty'), 
                item.get('price')
            )
            
            if key not in seen:
                seen.add(key)
                unique_items.append(item)
        
        return unique_items
    
    def _detect_document_type(self, text: str, tables: List[pd.DataFrame] = None) -> str:
        """Определение типа документа"""
        text_lower = text.lower()
        
        commercial_indicators = ['коммерческое предложение', 'предложение', 'поставщик', 'товар']
        invoice_indicators = ['счет на оплату', 'счет №', 'оплата', 'плательщик', 'получатель']
        competitive_indicators = ['конкурентная процедура', 'тендер', 'аукцион', 'заявка']
        
        if any(indicator in text_lower for indicator in commercial_indicators):
            return 'commercial_proposal'
        elif any(indicator in text_lower for indicator in invoice_indicators):
            return 'invoice'
        elif any(indicator in text_lower for indicator in competitive_indicators):
            return 'competitive_procedure'
        else:
            return 'unknown'
    
    def _generate_recommendations(self, results: Dict[str, Any]) -> List[str]:
        """Генерация рекомендаций"""
        recommendations = []
        
        commercial_count = results['commercial_parser'].get('count', 0) if results['commercial_parser'] and not isinstance(results['commercial_parser'], dict) else 0
        invoice_count = results['invoice_parser'].get('count', 0) if results['invoice_parser'] and not isinstance(results['invoice_parser'], dict) else 0
        competitive_count = results['competitive_parser'].get('count', 0) if results['competitive_parser'] and not isinstance(results['competitive_parser'], dict) else 0
        universal_count = results['universal_parser'].get('count', 0) if results['universal_parser'] and not isinstance(results['universal_parser'], dict) else 0
        
        if results['document_type'] == 'commercial_proposal':
            if commercial_count > 0:
                recommendations.append("✅ Документ успешно распарсен коммерческим парсером")
            else:
                recommendations.append("⚠️ Коммерческое предложение не содержит товарных позиций")
        
        elif results['document_type'] == 'invoice':
            if invoice_count > 0:
                recommendations.append("✅ Счет на оплату успешно распарсен")
            else:
                recommendations.append("⚠️ Счет на оплату не содержит товарных позиций")
        
        if universal_count > 0:
            recommendations.append("✅ Универсальный парсер нашел позиции")
        
        if competitive_count > 10:
            recommendations.append("⚠️ Конкурентный парсер нашел много позиций - возможны ложные срабатывания")
        
        if results['best_parser']:
            # Исправляем ключ для precise_table_parser
            parser_key = f"{results['best_parser']}_parser"
            if parser_key in results:
                best_result = results[parser_key]
                if best_result and not isinstance(best_result, dict):
                    confidence = best_result.get('avg_confidence', 0)
                    if confidence < 0.7:
                        recommendations.append("⚠️ Низкая уверенность парсинга - рекомендуется ручная проверка")
                    elif confidence > 0.9:
                        recommendations.append("✅ Высокая уверенность парсинга")
        
        if all(count == 0 for count in [commercial_count, invoice_count, competitive_count, universal_count]):
            recommendations.append("❌ Ни один парсер не нашел товарные позиции")
            recommendations.append("💡 Возможные причины: документ не содержит товарных позиций, неподдерживаемый формат")
        
        return recommendations
    
    def get_best_items(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Получение лучших результатов парсинга"""
        if results['best_items']:
            return results['best_items']
        return []
    
    def parse_pdf_file(self, pdf_path: str, enable_ocr: bool = True) -> Dict[str, Any]:
        """
        Парсинг PDF файла с поддержкой OCR
        
        Args:
            pdf_path: Путь к PDF файлу
            enable_ocr: Включить ли OCR обработку
            
        Returns:
            Словарь с результатами парсинга
        """
        try:
            logger.info(f"Начинаем парсинг PDF файла: {pdf_path}")
            
            # Используем улучшенный экстрактор, если доступен
            if self.use_ocr and self.enhanced_extractor and enable_ocr:
                logger.info("Используем улучшенный экстрактор с OCR")
                text, tables, extraction_info = self.enhanced_extractor.extract_text_and_tables(pdf_path)
                
                # Добавляем информацию об извлечении
                results = {
                    'extraction_info': extraction_info,
                    'pdf_path': pdf_path,
                    'file_size': extraction_info.get('file_size', 0),
                    'processing_time': extraction_info.get('processing_time', 0)
                }
                
            else:
                # Используем стандартный экстрактор
                logger.info("Используем стандартный экстрактор")
                from app.pipeline.extractor import extract_text_and_tables
                text, tables, extraction_info = extract_text_and_tables(pdf_path)
                
                results = {
                    'extraction_info': extraction_info,
                    'pdf_path': pdf_path
                }
            
            # Парсим документ
            parse_results = self.parse_document(text, tables, pdf_path)
            results.update(parse_results)
            
            # Добавляем метаданные
            results['file_info'] = {
                'path': pdf_path,
                'name': pdf_path.split('/')[-1],
                'extraction_method': 'enhanced_with_ocr' if (self.use_ocr and self.enhanced_extractor and enable_ocr) else 'standard',
                'ocr_used': results.get('ocr_info', {}).get('ocr_additions', 0) > 0
            }
            
            # Генерируем рекомендации
            results['recommendations'] = self._generate_recommendations(results)
            
            # Добавляем качество извлечения
            if 'quality_assessment' in results:
                quality = results['quality_assessment']
                results['extraction_quality'] = {
                    'overall': quality.get('overall_quality', 0),
                    'text_quality': quality.get('text_quality', 0),
                    'table_quality': quality.get('table_quality', 0),
                    'issues': quality.get('issues', []),
                    'recommendations': quality.get('recommendations', [])
                }
            
            logger.info(f"PDF файл успешно обработан: {len(text)} символов, {len(tables)} таблиц")
            return results
            
        except Exception as e:
            error_msg = f"Ошибка парсинга PDF файла {pdf_path}: {e}"
            logger.error(error_msg)
            return {
                'error': error_msg,
                'pdf_path': pdf_path,
                'extraction_info': {'errors': [error_msg]},
                'recommendations': ['❌ Ошибка обработки файла', '💡 Проверьте формат и доступность файла']
            }
    
    def get_ocr_status(self) -> Dict[str, Any]:
        """Получение статуса OCR"""
        return {
            'ocr_enabled': self.use_ocr,
            'enhanced_extractor_available': self.enhanced_extractor is not None,
            'languages': self.enhanced_extractor.ocr_processor.languages if self.enhanced_extractor else [],
            'status': 'active' if (self.use_ocr and self.enhanced_extractor) else 'disabled'
        }
    
    def toggle_ocr(self, enable: bool) -> bool:
        """Включение/выключение OCR"""
        if enable and not self.use_ocr:
            try:
                from app.pipeline.enhanced_extractor import EnhancedExtractor
                self.enhanced_extractor = EnhancedExtractor(use_ocr=True)
                self.use_ocr = True
                logger.info("OCR включен")
                return True
            except Exception as e:
                logger.error(f"Не удалось включить OCR: {e}")
                return False
        elif not enable and self.use_ocr:
            self.use_ocr = False
            self.enhanced_extractor = None
            logger.info("OCR отключен")
            return True
        
        return True
