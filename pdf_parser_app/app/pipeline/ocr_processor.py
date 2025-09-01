"""
OCR (Optical Character Recognition) processor for PDF documents
"""

import logging
import io
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import fitz  # PyMuPDF
import cv2
import numpy as np
from PIL import Image
import easyocr
import re

logger = logging.getLogger(__name__)

class OCRProcessor:
    """OCR процессор для извлечения текста из изображений в PDF"""
    
    def __init__(self, languages: List[str] = None):
        """
        Инициализация OCR процессора
        
        Args:
            languages: Список языков для распознавания (по умолчанию ['ru', 'en'])
        """
        self.languages = languages or ['ru', 'en']
        self.reader = None
        self._initialize_ocr()
    
    def _initialize_ocr(self):
        """Инициализация EasyOCR"""
        try:
            self.reader = easyocr.Reader(self.languages, gpu=False)
            logger.info(f"OCR инициализирован для языков: {self.languages}")
        except Exception as e:
            logger.error(f"Ошибка инициализации OCR: {e}")
            self.reader = None
    
    def extract_images_from_pdf(self, pdf_path: str) -> List[Tuple[np.ndarray, int]]:
        """
        Извлекает изображения из PDF
        
        Args:
            pdf_path: Путь к PDF файлу
            
        Returns:
            Список кортежей (изображение, номер страницы)
        """
        images = []
        
        try:
            doc = fitz.open(pdf_path)
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Получаем список изображений на странице
                image_list = page.get_images()
                
                for img_index, img in enumerate(image_list):
                    try:
                        # Извлекаем изображение
                        xref = img[0]
                        pix = fitz.Pixmap(doc, xref)
                        
                        if pix.n - pix.alpha < 4:  # RGB или RGBA
                            img_data = pix.tobytes("png")
                            nparr = np.frombuffer(img_data, np.uint8)
                            cv_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                            
                            if cv_img is not None:
                                images.append((cv_img, page_num + 1))
                                logger.debug(f"Извлечено изображение {img_index + 1} со страницы {page_num + 1}")
                        
                        pix = None  # Освобождаем память
                        
                    except Exception as e:
                        logger.warning(f"Ошибка извлечения изображения {img_index + 1} со страницы {page_num + 1}: {e}")
                        continue
            
            doc.close()
            logger.info(f"Извлечено {len(images)} изображений из PDF")
            
        except Exception as e:
            logger.error(f"Ошибка извлечения изображений из PDF: {e}")
        
        return images
    
    def process_image_with_ocr(self, image: np.ndarray) -> str:
        """
        Обрабатывает изображение с помощью OCR
        
        Args:
            image: Изображение в формате numpy array
            
        Returns:
            Распознанный текст
        """
        if self.reader is None:
            logger.warning("OCR не инициализирован")
            return ""
        
        try:
            # Предобработка изображения
            processed_image = self._preprocess_image(image)
            
            # OCR распознавание
            results = self.reader.readtext(processed_image)
            
            # Извлекаем текст из результатов
            text_parts = []
            for (bbox, text, confidence) in results:
                if confidence > 0.5:  # Фильтруем по уверенности
                    text_parts.append(text.strip())
            
            extracted_text = " ".join(text_parts)
            logger.debug(f"OCR распознал {len(text_parts)} текстовых блоков")
            
            return extracted_text
            
        except Exception as e:
            logger.error(f"Ошибка OCR обработки: {e}")
            return ""
    
    def _preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """
        Предобработка изображения для улучшения OCR
        
        Args:
            image: Исходное изображение
            
        Returns:
            Обработанное изображение
        """
        try:
            # Конвертируем в оттенки серого
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()
            
            # Увеличиваем контраст
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            enhanced = clahe.apply(gray)
            
            # Убираем шум
            denoised = cv2.medianBlur(enhanced, 3)
            
            # Бинаризация
            _, binary = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            return binary
            
        except Exception as e:
            logger.warning(f"Ошибка предобработки изображения: {e}")
            return image
    
    def enhance_pdf_text(self, pdf_path: str, original_text: str) -> Tuple[str, Dict[str, Any]]:
        """
        Улучшает текст PDF с помощью OCR
        
        Args:
            pdf_path: Путь к PDF файлу
            original_text: Исходный текст
            
        Returns:
            Кортеж (улучшенный_текст, информация_об_улучшении)
        """
        enhancement_info = {
            'original_length': len(original_text),
            'ocr_additions': 0,
            'images_processed': 0,
            'total_ocr_text': 0
        }
        
        enhanced_text = original_text
        
        try:
            # Извлекаем изображения
            images = self.extract_images_from_pdf(pdf_path)
            enhancement_info['images_processed'] = len(images)
            
            if not images:
                logger.info("Изображения для OCR не найдены")
                return enhanced_text, enhancement_info
            
            # Обрабатываем каждое изображение
            ocr_texts = []
            for image, page_num in images:
                ocr_text = self.process_image_with_ocr(image)
                if ocr_text:
                    ocr_texts.append(f"[Страница {page_num} OCR]: {ocr_text}")
                    enhancement_info['total_ocr_text'] += len(ocr_text)
            
            # Добавляем OCR текст к основному
            if ocr_texts:
                enhanced_text += "\n\n" + "\n".join(ocr_texts)
                enhancement_info['ocr_additions'] = len(ocr_texts)
                
                logger.info(f"OCR добавил {len(ocr_texts)} текстовых блоков")
            
        except Exception as e:
            logger.error(f"Ошибка улучшения текста с OCR: {e}")
        
        return enhanced_text, enhancement_info
    
    def detect_document_type(self, text: str) -> Dict[str, float]:
        """
        Определяет тип документа на основе текста
        
        Args:
            text: Текст документа
            
        Returns:
            Словарь с типами документов и уверенностью
        """
        document_types = {
            'invoice': 0.0,
            'commercial_proposal': 0.0,
            'competitive_document': 0.0,
            'contract': 0.0
        }
        
        # Ключевые слова для счетов
        invoice_keywords = [
            'счет', 'счет-фактура', 'invoice', 'bill', 'оплата', 'платеж',
            'ндс', 'итого', 'сумма', 'к оплате', 'банковские реквизиты'
        ]
        
        # Ключевые слова для коммерческих предложений
        commercial_keywords = [
            'коммерческое предложение', 'commercial proposal', 'предложение',
            'условия поставки', 'сроки поставки', 'гарантия', 'спецификация'
        ]
        
        # Ключевые слова для конкурсной документации
        competitive_keywords = [
            'конкурс', 'тендер', 'аукцион', 'заявка', 'предложение',
            'техническое задание', 'тз', 'спецификация'
        ]
        
        # Ключевые слова для договоров
        contract_keywords = [
            'договор', 'контракт', 'соглашение', 'contract', 'agreement',
            'стороны', 'обязательства', 'ответственность', 'форс-мажор'
        ]
        
        text_lower = text.lower()
        
        # Подсчитываем совпадения для каждого типа
        for keyword in invoice_keywords:
            if keyword in text_lower:
                document_types['invoice'] += 1
        
        for keyword in commercial_keywords:
            if keyword in text_lower:
                document_types['commercial_proposal'] += 1
        
        for keyword in competitive_keywords:
            if keyword in text_lower:
                document_types['competitive_document'] += 1
        
        for keyword in contract_keywords:
            if keyword in text_lower:
                document_types['contract'] += 1
        
        # Нормализуем значения
        total_keywords = sum(document_types.values())
        if total_keywords > 0:
            for doc_type in document_types:
                document_types[doc_type] = document_types[doc_type] / total_keywords
        
        return document_types
    
    def validate_extracted_data(self, text: str, tables: List) -> Dict[str, Any]:
        """
        Валидирует извлеченные данные
        
        Args:
            text: Текст документа
            tables: Извлеченные таблицы
            
        Returns:
            Словарь с результатами валидации
        """
        validation_results = {
            'text_quality': 0.0,
            'table_quality': 0.0,
            'overall_quality': 0.0,
            'issues': [],
            'recommendations': []
        }
        
        # Проверяем качество текста
        if text:
            # Проверяем наличие ключевых элементов
            key_elements = ['товар', 'цена', 'количество', 'сумма', 'итого']
            found_elements = sum(1 for element in key_elements if element in text.lower())
            validation_results['text_quality'] = found_elements / len(key_elements)
            
            if validation_results['text_quality'] < 0.6:
                validation_results['issues'].append("Низкое качество извлеченного текста")
                validation_results['recommendations'].append("Попробуйте OCR для улучшения качества")
        
        # Проверяем качество таблиц
        if tables:
            valid_tables = sum(1 for table in tables if len(table) > 1 and len(table.columns) > 2)
            validation_results['table_quality'] = valid_tables / len(tables) if tables else 0.0
            
            if validation_results['table_quality'] < 0.5:
                validation_results['issues'].append("Проблемы с извлечением таблиц")
                validation_results['recommendations'].append("Проверьте структуру PDF")
        
        # Общее качество
        validation_results['overall_quality'] = (
            validation_results['text_quality'] + validation_results['table_quality']
        ) / 2
        
        return validation_results
