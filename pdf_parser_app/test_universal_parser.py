#!/usr/bin/env python3
"""
Тест универсального парсера с интеграцией всех парсеров
"""

import os
import sys
import logging
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

from app.pipeline.universal_parser import UniversalParser
from app.pipeline.detector import detect_text_layer
from app.pipeline.extractor import extract_text_and_tables
from app.db.database import init_database

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)

def test_universal_parser():
    """Тестирует универсальный парсер на всех файлах"""
    print("\n🔧 ТЕСТ УНИВЕРСАЛЬНОГО ПАРСЕРА")
    print("=" * 60)
    
    # Инициализируем базу данных
    init_database()
    
    # Создаем парсер
    parser = UniversalParser()
    
    # Папка с тестовыми файлами
    inbox_dir = Path("inbox")
    
    if not inbox_dir.exists():
        print("❌ Папка inbox не найдена")
        return
    
    # Получаем список PDF файлов
    pdf_files = list(inbox_dir.glob("*.pdf"))
    
    if not pdf_files:
        print("❌ PDF файлы не найдены в папке inbox")
        return
    
    print(f"📁 Найдено {len(pdf_files)} PDF файлов")
    
    total_processed = 0
    total_items_found = 0
    
    for pdf_file in pdf_files:
        print(f"\n📄 Обработка файла: {pdf_file.name}")
        print("-" * 50)
        
        try:
            # Проверяем наличие текстового слоя
            has_text, char_count, info = detect_text_layer(str(pdf_file))
            
            if has_text:
                print(f"✅ Текстовый слой найден ({char_count} символов)")
            else:
                print(f"⚠️ Текстовый слой не найден")
            
            # Извлекаем текст и таблицы
            text, tables, metadata = extract_text_and_tables(str(pdf_file))
            print(f"📊 Извлечено таблиц: {len(tables)}")
            
            # Парсим документ
            results = parser.parse_document(text, tables)
            
            # Анализируем результаты
            best_parser = results.get('best_parser')
            best_items = results.get('best_items', [])
            document_type = results.get('document_type')
            
            print(f"🎯 Лучший парсер: {best_parser}")
            print(f"📋 Тип документа: {document_type}")
            print(f"📦 Найдено позиций: {len(best_items)}")
            
            if best_items:
                total_cost = sum(item.get('total', 0) for item in best_items)
                avg_confidence = sum(item.get('confidence', 0) for item in best_items) / len(best_items)
                print(f"💰 Общая стоимость: {total_cost:,.2f} руб.")
                print(f"🎯 Средняя уверенность: {avg_confidence:.1%}")
                
                print(f"\n📋 НАЙДЕННЫЕ ПОЗИЦИИ:")
                for i, item in enumerate(best_items, 1):
                    name = item.get('name', 'N/A')
                    qty = item.get('qty', 'N/A')
                    unit = item.get('unit', '')
                    price = item.get('price', 'N/A')
                    total = item.get('total', 'N/A')
                    article = item.get('article', '')
                    
                    print(f"  {i}. {name}")
                    if article:
                        print(f"     Артикул: {article}")
                    print(f"     Количество: {qty} {unit}")
                    print(f"     Цена: {price:,.2f} руб.")
                    print(f"     Сумма: {total:,.2f} руб.")
                    print()
                
                total_items_found += len(best_items)
            else:
                print(f"❌ Позиции не найдены")
                
                # Показываем результаты всех парсеров
                print(f"\n🔍 РЕЗУЛЬТАТЫ ВСЕХ ПАРСЕРОВ:")
                parsers = ['commercial_parser', 'invoice_parser', 'competitive_parser', 
                          'universal_parser', 'supplier_profile_parser', 'table_extractor', 'precise_table_parser']
                
                for parser_name in parsers:
                    parser_result = results.get(parser_name, {})
                    if 'error' in parser_result:
                        print(f"  {parser_name}: ❌ {parser_result['error']}")
                    else:
                        count = parser_result.get('count', 0)
                        total_cost = parser_result.get('total_cost', 0)
                        avg_confidence = parser_result.get('avg_confidence', 0)
                        print(f"  {parser_name}: {count} позиций, {total_cost:,.2f} руб., {avg_confidence:.1%}")
            
            total_processed += 1
            
        except Exception as e:
            print(f"❌ Ошибка обработки файла: {e}")
            continue
    
    print(f"\n🎉 ТЕСТ ЗАВЕРШЕН!")
    print(f"📊 Обработано файлов: {total_processed}")
    print(f"📦 Всего найдено позиций: {total_items_found}")

if __name__ == "__main__":
    test_universal_parser()
