#!/usr/bin/env python3
"""
Тестовый скрипт для проверки OCR функциональности
"""

import sys
import os
from pathlib import Path

# Добавляем путь к модулям приложения
sys.path.insert(0, str(Path(__file__).parent / "app"))

def test_ocr_processor():
    """Тестирует OCR процессор"""
    print("🧪 Тестирование OCR процессора...")
    
    try:
        from pipeline.ocr_processor import OCRProcessor
        
        # Инициализируем OCR
        ocr = OCRProcessor(['ru', 'en'])
        
        if ocr.reader is None:
            print("❌ OCR не инициализирован")
            return False
        
        print("✅ OCR процессор успешно инициализирован")
        
        # Тестируем определение типа документа
        test_text = "Счет на оплату №123 от 01.01.2025"
        doc_type = ocr.detect_document_type(test_text)
        print(f"📄 Тип документа: {doc_type}")
        
        # Тестируем валидацию
        validation = ocr.validate_extracted_data(test_text, [])
        print(f"✅ Валидация: {validation}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка тестирования OCR: {e}")
        return False

def test_enhanced_extractor():
    """Тестирует улучшенный экстрактор"""
    print("\n🧪 Тестирование улучшенного экстрактора...")
    
    try:
        from pipeline.enhanced_extractor import EnhancedExtractor
        
        # Инициализируем экстрактор
        extractor = EnhancedExtractor(use_ocr=True)
        
        if extractor.ocr_processor is None:
            print("⚠️ OCR отключен в экстракторе")
        else:
            print("✅ Улучшенный экстрактор с OCR успешно инициализирован")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка тестирования экстрактора: {e}")
        return False

def test_with_sample_pdf():
    """Тестирует с реальным PDF файлом"""
    print("\n🧪 Тестирование с реальным PDF...")
    
    # Ищем PDF файлы в папке inbox
    inbox_path = Path("inbox")
    pdf_files = list(inbox_path.glob("*.pdf"))
    
    if not pdf_files:
        print("⚠️ PDF файлы не найдены в папке inbox")
        return False
    
    # Берем первый PDF файл
    test_pdf = pdf_files[0]
    print(f"📄 Тестируем файл: {test_pdf.name}")
    
    try:
        from pipeline.enhanced_extractor import EnhancedExtractor
        
        extractor = EnhancedExtractor(use_ocr=True)
        
        # Извлекаем текст и таблицы
        text, tables, info = extractor.extract_text_and_tables(str(test_pdf))
        
        print(f"📝 Извлечено символов: {len(text)}")
        print(f"📊 Найдено таблиц: {len(tables)}")
        print(f"🔍 OCR использован: {info.get('ocr_used', False)}")
        
        if info.get('ocr_used'):
            ocr_info = info.get('ocr_enhancements', {})
            print(f"🔍 OCR улучшения: {ocr_info}")
        
        # Показываем резюме
        summary = extractor.get_extraction_summary(info)
        print(f"\n📋 Резюме извлечения:\n{summary}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка обработки PDF: {e}")
        return False

def main():
    """Основная функция тестирования"""
    print("🚀 Запуск тестов OCR функциональности\n")
    
    # Тест 1: OCR процессор
    test1_passed = test_ocr_processor()
    
    # Тест 2: Улучшенный экстрактор
    test2_passed = test_enhanced_extractor()
    
    # Тест 3: Реальный PDF
    test3_passed = test_with_sample_pdf()
    
    # Итоги
    print("\n" + "="*50)
    print("📊 ИТОГИ ТЕСТИРОВАНИЯ:")
    print(f"OCR процессор: {'✅' if test1_passed else '❌'}")
    print(f"Улучшенный экстрактор: {'✅' if test2_passed else '❌'}")
    print(f"Обработка PDF: {'✅' if test3_passed else '❌'}")
    
    if all([test1_passed, test2_passed, test3_passed]):
        print("\n🎉 Все тесты пройдены успешно!")
        print("OCR функциональность готова к использованию!")
    else:
        print("\n⚠️ Некоторые тесты не пройдены")
        print("Проверьте установку зависимостей и настройки")

if __name__ == "__main__":
    main()
