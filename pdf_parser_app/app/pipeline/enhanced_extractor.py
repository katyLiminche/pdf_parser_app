"""
Enhanced PDF text and table extraction with OCR support
"""

import logging
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
import pdfplumber
import pandas as pd
from .ocr_processor import OCRProcessor
import numpy as np

logger = logging.getLogger(__name__)

class EnhancedExtractor:
    """Улучшенный экстрактор с поддержкой OCR"""
    
    def __init__(self, use_ocr: bool = True, ocr_languages: List[str] = None):
        """
        Инициализация улучшенного экстрактора
        
        Args:
            use_ocr: Использовать ли OCR
            ocr_languages: Языки для OCR
        """
        self.use_ocr = use_ocr
        self.ocr_processor = None
        
        if self.use_ocr:
            try:
                self.ocr_processor = OCRProcessor(ocr_languages)
                logger.info("OCR процессор инициализирован")
            except Exception as e:
                logger.warning(f"Не удалось инициализировать OCR: {e}")
                self.use_ocr = False
    
    def extract_text_and_tables(self, pdf_path: str, enable_ocr_fallback: bool = True) -> Tuple[str, List[pd.DataFrame], Dict[str, Any]]:
        """
        Извлекает текст и таблицы с поддержкой OCR
        
        Args:
            pdf_path: Путь к PDF файлу
            enable_ocr_fallback: Включить ли OCR как fallback
            
        Returns:
            Кортеж (текст, таблицы, информация_об_извлечении)
        """
        extraction_info = {
            'page_count': 0,
            'total_chars': 0,
            'tables_found': 0,
            'ocr_used': False,
            'ocr_enhancements': {},
            'extraction_method': 'standard',
            'errors': []
        }
        
        try:
            # Стандартное извлечение с pdfplumber
            text, tables, basic_info = self._extract_with_pdfplumber(pdf_path)
            extraction_info.update(basic_info)
            
            # Проверяем качество извлеченного текста
            if self.use_ocr and enable_ocr_fallback:
                quality_check = self._check_text_quality(text, tables)
                
                # Если качество низкое, используем OCR
                if quality_check['needs_ocr']:
                    logger.info("Качество текста низкое, применяем OCR")
                    enhanced_text, ocr_info = self.ocr_processor.enhance_pdf_text(pdf_path, text)
                    
                    if ocr_info['ocr_additions'] > 0:
                        text = enhanced_text
                        extraction_info['ocr_used'] = True
                        extraction_info['ocr_enhancements'] = ocr_info
                        extraction_info['extraction_method'] = 'hybrid'
                        extraction_info['total_chars'] = len(text)
                        
                        logger.info(f"OCR улучшил текст: добавлено {ocr_info['ocr_additions']} блоков")
                
                # Определяем тип документа
                doc_type = self.ocr_processor.detect_document_type(text)
                extraction_info['document_type'] = doc_type
                
                # Валидируем результат
                validation = self.ocr_processor.validate_extracted_data(text, tables)
                extraction_info['validation'] = validation
            
            return text, tables, extraction_info
            
        except Exception as e:
            error_msg = f"Ошибка извлечения из PDF {pdf_path}: {e}"
            logger.error(error_msg)
            extraction_info['errors'].append(error_msg)
            return "", [], extraction_info
    
    def _extract_with_pdfplumber(self, pdf_path: str) -> Tuple[str, List[pd.DataFrame], Dict[str, Any]]:
        """Стандартное извлечение с pdfplumber"""
        pages_text = []
        tables = []
        extraction_info = {
            'page_count': 0,
            'total_chars': 0,
            'tables_found': 0,
            'errors': []
        }
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                extraction_info['page_count'] = len(pdf.pages)
                
                for page_num, page in enumerate(pdf.pages):
                    try:
                        # Извлекаем текст
                        text = page.extract_text() or ""
                        pages_text.append(text)
                        extraction_info['total_chars'] += len(text)
                        
                        # Извлекаем таблицы
                        page_tables = self._extract_tables_from_page(page, page_num)
                        tables.extend(page_tables)
                        
                    except Exception as e:
                        error_msg = f"Ошибка обработки страницы {page_num + 1}: {e}"
                        logger.warning(error_msg)
                        extraction_info['errors'].append(error_msg)
                        continue
                
                extraction_info['tables_found'] = len(tables)
                
                # Объединяем весь текст
                full_text = "\n\n".join(pages_text)
                
                logger.info(f"Извлечено {extraction_info['total_chars']} символов и {len(tables)} таблиц")
                
                return full_text, tables, extraction_info
                
        except Exception as e:
            error_msg = f"Не удалось извлечь из PDF {pdf_path}: {e}"
            logger.error(error_msg)
            extraction_info['errors'].append(error_msg)
            return "", [], extraction_info
    
    def _extract_tables_from_page(self, page, page_num: int) -> List[pd.DataFrame]:
        """Извлекает таблицы со страницы"""
        tables = []
        
        try:
            # Метод 1: Встроенное извлечение таблиц pdfplumber
            page_tables = page.extract_tables()
            
            for table_idx, table_data in enumerate(page_tables):
                if table_data and len(table_data) > 1:  # Минимум заголовок + 1 строка
                    try:
                        # Конвертируем в DataFrame
                        df = pd.DataFrame(table_data[1:], columns=table_data[0])
                        
                        # Базовая валидация
                        if self._is_valid_table(df):
                            df['_page'] = page_num + 1
                            df['_table_id'] = table_idx + 1
                            tables.append(df)
                            logger.debug(f"Страница {page_num + 1}, Таблица {table_idx + 1}: {len(df)} строк, {len(df.columns)} колонок")
                        else:
                            logger.debug(f"Страница {page_num + 1}, Таблица {table_idx + 1}: Отклонена (неверная структура)")
                            
                    except Exception as e:
                        logger.warning(f"Ошибка обработки таблицы {table_idx + 1} на странице {page_num + 1}: {e}")
                        continue
            
            # Метод 2: Попытка извлечения по координатам (для сложных таблиц)
            if not tables:
                tables = self._extract_tables_by_coordinates(page, page_num)
            
        except Exception as e:
            logger.warning(f"Ошибка извлечения таблиц со страницы {page_num + 1}: {e}")
        
        return tables
    
    def _extract_tables_by_coordinates(self, page, page_num: int) -> List[pd.DataFrame]:
        """Извлекает таблицы по координатам (для сложных случаев)"""
        tables = []
        
        try:
            # Получаем все текстовые блоки с координатами
            words = page.extract_words()
            
            if not words:
                return tables
            
            # Группируем слова по строкам (по Y координате)
            y_tolerance = 5  # Допуск по Y координате
            lines = {}
            
            for word in words:
                y_key = round(word['top'] / y_tolerance) * y_tolerance
                if y_key not in lines:
                    lines[y_key] = []
                lines[y_key].append(word)
            
            # Сортируем строки по Y координате
            sorted_lines = sorted(lines.items())
            
            # Создаем таблицу
            if len(sorted_lines) > 1:
                table_data = []
                for y, line_words in sorted_lines:
                    # Сортируем слова в строке по X координате
                    line_words.sort(key=lambda w: w['x0'])
                    row = [word['text'] for word in line_words]
                    table_data.append(row)
                
                # Создаем DataFrame
                if table_data:
                    df = pd.DataFrame(table_data)
                    df['_page'] = page_num + 1
                    df['_table_id'] = 1
                    tables.append(df)
                    logger.debug(f"Извлечена таблица по координатам: {len(df)} строк, {len(df.columns)} колонок")
        
        except Exception as e:
            logger.warning(f"Ошибка извлечения таблиц по координатам: {e}")
        
        return tables
    
    def _is_valid_table(self, df: pd.DataFrame) -> bool:
        """Проверяет, является ли DataFrame валидной таблицей"""
        if df.empty or len(df.columns) < 2:
            return False
        
        # Проверяем, что есть числовые данные
        numeric_columns = df.select_dtypes(include=[np.number]).columns
        if len(numeric_columns) == 0:
            # Проверяем, есть ли строки, которые можно преобразовать в числа
            numeric_like = 0
            for col in df.columns:
                try:
                    pd.to_numeric(df[col].astype(str).str.replace(',', '.'), errors='coerce')
                    numeric_like += 1
                except:
                    pass
            
            if numeric_like == 0:
                return False
        
        return True
    
    def _check_text_quality(self, text: str, tables: List[pd.DataFrame]) -> Dict[str, Any]:
        """Проверяет качество извлеченного текста"""
        quality_info = {
            'needs_ocr': False,
            'text_length': len(text),
            'table_count': len(tables),
            'issues': []
        }
        
        # Проверяем длину текста
        if len(text.strip()) < 100:
            quality_info['needs_ocr'] = True
            quality_info['issues'].append("Слишком короткий текст")
        
        # Проверяем наличие ключевых слов
        key_words = ['товар', 'цена', 'количество', 'сумма', 'итого', 'ндс']
        found_words = sum(1 for word in key_words if word in text.lower())
        
        if found_words < 2:
            quality_info['needs_ocr'] = True
            quality_info['issues'].append("Недостаточно ключевых слов")
        
        # Проверяем качество таблиц
        if tables:
            valid_tables = sum(1 for table in tables if len(table) > 1 and len(table.columns) > 2)
            if valid_tables == 0:
                quality_info['needs_ocr'] = True
                quality_info['issues'].append("Нет валидных таблиц")
        
        return quality_info
    
    def get_extraction_summary(self, extraction_info: Dict[str, Any]) -> str:
        """Формирует краткое резюме извлечения"""
        summary = f"📄 Извлечено {extraction_info['page_count']} страниц\n"
        summary += f"📝 {extraction_info['total_chars']} символов текста\n"
        summary += f"📊 {extraction_info['tables_found']} таблиц\n"
        
        if extraction_info.get('ocr_used'):
            ocr_info = extraction_info.get('ocr_enhancements', {})
            summary += f"🔍 OCR добавлено {ocr_info.get('ocr_additions', 0)} текстовых блоков\n"
        
        if extraction_info.get('validation'):
            validation = extraction_info['validation']
            summary += f"✅ Общее качество: {validation['overall_quality']:.1%}\n"
            
            if validation['issues']:
                summary += f"⚠️ Проблемы: {', '.join(validation['issues'])}\n"
        
        return summary
