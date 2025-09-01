#!/usr/bin/env python3
"""
Простой тест OCR на одном PDF файле
"""

import sys
import os
import time
from pathlib import Path

# Добавляем путь к модулям приложения
sys.path.insert(0, str(Path(__file__).parent / "app"))

def test_single_pdf(pdf_path: str):
    """Тестирует OCR на одном PDF файле"""
    
    print(f"🧪 Тестирование OCR на файле: {Path(pdf_path).name}")
    print("=" * 60)
    
    try:
        from app.pipeline.universal_parser import UniversalParser
        
        # Тест 1: Без OCR
        print("📊 ТЕСТ БЕЗ OCR:")
        start_time = time.time()
        
        parser_no_ocr = UniversalParser(use_ocr=False)
        result_no_ocr = parser_no_ocr.parse_pdf_file(pdf_path, enable_ocr=False)
        
        time_no_ocr = time.time() - start_time
        
        if 'error' in result_no_ocr:
            print(f"❌ Ошибка без OCR: {result_no_ocr['error']}")
        else:
            print(f"✅ Успешно без OCR за {time_no_ocr:.2f} сек")
            print(f"   Символов: {result_no_ocr.get('extraction_info', {}).get('total_chars', 0):,}")
            print(f"   Таблиц: {result_no_ocr.get('extraction_info', {}).get('tables_found', 0)}")
            print(f"   Позиций: {len(result_no_ocr.get('best_items', []))}")
        
        print("\n" + "-" * 40)
        
        # Тест 2: С OCR
        print("📊 ТЕСТ С OCR:")
        start_time = time.time()
        
        parser_with_ocr = UniversalParser(use_ocr=True, ocr_languages=['ru', 'en'])
        result_with_ocr = parser_with_ocr.parse_pdf_file(pdf_path, enable_ocr=True)
        
        time_with_ocr = time.time() - start_time
        
        if 'error' in result_with_ocr:
            print(f"❌ Ошибка с OCR: {result_with_ocr['error']}")
        else:
            print(f"✅ Успешно с OCR за {time_with_ocr:.2f} сек")
            print(f"   Символов: {result_with_ocr.get('extraction_info', {}).get('total_chars', 0):,}")
            print(f"   Таблиц: {result_with_ocr.get('extraction_info', {}).get('tables_found', 0)}")
            print(f"   Позиций: {len(result_with_ocr.get('best_items', []))}")
            
            # OCR информация
            ocr_info = result_with_ocr.get('ocr_info', {})
            if ocr_info and ocr_info.get('ocr_additions', 0) > 0:
                print(f"   OCR улучшения: +{ocr_info['ocr_additions']} текстовых блоков")
                print(f"   Обработано изображений: {ocr_info.get('images_processed', 0)}")
            
            # Качество
            quality = result_with_ocr.get('extraction_quality', {})
            if quality:
                print(f"   Общее качество: {quality.get('overall_quality', 0):.1%}")
        
        # Сравнение
        print("\n📈 СРАВНЕНИЕ:")
        if 'error' not in result_no_ocr and 'error' not in result_with_ocr:
            chars_no_ocr = result_no_ocr.get('extraction_info', {}).get('total_chars', 0)
            chars_with_ocr = result_with_ocr.get('extraction_info', {}).get('total_chars', 0)
            
            print(f"   Символов без OCR: {chars_no_ocr:,}")
            print(f"   Символов с OCR: {chars_with_ocr:,}")
            print(f"   Разница: {chars_with_ocr - chars_no_ocr:+,}")
            
            print(f"   Время без OCR: {time_no_ocr:.2f} сек")
            print(f"   Время с OCR: {time_with_ocr:.2f} сек")
            print(f"   Разница: {time_with_ocr - time_no_ocr:+.2f} сек")
            
            if time_with_ocr > time_no_ocr:
                print(f"   OCR замедлил обработку в {time_with_ocr/time_no_ocr:.1f} раз")
            else:
                print(f"   OCR ускорил обработку в {time_no_ocr/time_with_ocr:.1f} раз")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Основная функция"""
    
    # Получаем список PDF файлов из inbox
    inbox_path = Path("inbox")
    pdf_files = list(inbox_path.glob("*.pdf"))
    
    if not pdf_files:
        print("❌ PDF файлы не найдены в папке inbox")
        return
    
    print(f"📁 Найдено {len(pdf_files)} PDF файлов:")
    for i, pdf_file in enumerate(pdf_files, 1):
        size_kb = pdf_file.stat().st_size / 1024
        print(f"   {i}. {pdf_file.name} ({size_kb:.1f} KB)")
    
    # Выбираем файл для тестирования (можно изменить индекс)
    test_index = 4  # Измените на 0, 1, 2 или 3 для тестирования разных файлов
    test_file = pdf_files[test_index - 1]
    
    print(f"\n🚀 Тестирование OCR на файле: {test_file.name}")
    print(f"📁 Путь: {test_file}")
    print(f"📏 Размер: {test_file.stat().st_size / 1024:.1f} KB")
    
    success = test_single_pdf(str(test_file))
    
    if success:
        print("\n🎉 Тестирование завершено успешно!")
    else:
        print("\n⚠️ Тестирование завершено с ошибками")

if __name__ == "__main__":
    main()
