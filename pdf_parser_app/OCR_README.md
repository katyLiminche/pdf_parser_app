# 🔍 OCR (Optical Character Recognition) для PDF Parser App

## 📋 Обзор

OCR модуль значительно улучшает качество парсинга PDF документов, особенно для:
- Отсканированных документов
- PDF с изображениями текста
- Документов с нестандартными шрифтами
- Сложных таблиц и форм

## 🚀 Установка

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 2. Проверка установки

```bash
python test_ocr.py
```

## 🏗️ Архитектура

```
PDF → Text Extraction (pdfplumber) → OCR Fallback → Enhanced Parser
```

### Компоненты:

- **`OCRProcessor`** - основной OCR процессор
- **`EnhancedExtractor`** - улучшенный экстрактор с OCR
- **Интеграция** с существующими парсерами

## 🔧 Использование

### Базовое использование:

```python
from app.pipeline.enhanced_extractor import EnhancedExtractor

# Инициализация с OCR
extractor = EnhancedExtractor(use_ocr=True, ocr_languages=['ru', 'en'])

# Извлечение текста и таблиц
text, tables, info = extractor.extract_text_and_tables("path/to/document.pdf")

# Получение резюме
summary = extractor.get_extraction_summary(info)
print(summary)
```

### Прямое использование OCR:

```python
from app.pipeline.ocr_processor import OCRProcessor

ocr = OCRProcessor(['ru', 'en'])

# Улучшение текста с OCR
enhanced_text, ocr_info = ocr.enhance_pdf_text("path/to/document.pdf", original_text)

# Определение типа документа
doc_type = ocr.detect_document_type(enhanced_text)

# Валидация данных
validation = ocr.validate_extracted_data(enhanced_text, tables)
```

## ⚙️ Настройки

### Языки OCR:
- **Русский** (`ru`) - основной язык
- **Английский** (`en`) - дополнительный язык
- **Другие** - можно добавить по необходимости

### Качество OCR:
- **Порог уверенности**: 0.5 (настраивается)
- **Предобработка изображений**: автоматическая
- **Фильтрация шума**: включена

## 📊 Возможности

### 1. Автоматическое определение качества
- Анализ длины текста
- Проверка ключевых слов
- Валидация таблиц

### 2. Умный fallback
- OCR включается только при необходимости
- Гибридный режим (стандартный + OCR)
- Оптимизация производительности

### 3. Анализ документов
- Определение типа документа
- Валидация извлеченных данных
- Рекомендации по улучшению

## 🧪 Тестирование

### Запуск тестов:
```bash
python test_ocr.py
```

### Тесты включают:
- Инициализацию OCR процессора
- Работу улучшенного экстрактора
- Обработку реальных PDF файлов

## 📈 Производительность

### Время обработки:
- **Стандартный режим**: ~1-2 сек на страницу
- **OCR режим**: ~3-5 сек на страницу
- **Гибридный режим**: ~2-3 сек на страницу

### Память:
- **EasyOCR**: ~500MB при инициализации
- **PyMuPDF**: ~100MB на документ
- **OpenCV**: ~50MB

## 🔍 Примеры использования

### Пример 1: Улучшение качества текста
```python
# Если стандартное извлечение дало плохой результат
if len(text) < 100:
    enhanced_text, ocr_info = ocr.enhance_pdf_text(pdf_path, text)
    print(f"OCR добавил {ocr_info['ocr_additions']} текстовых блоков")
```

### Пример 2: Определение типа документа
```python
doc_type = ocr.detect_document_type(text)
if doc_type['invoice'] > 0.7:
    print("Это счет-фактура")
elif doc_type['commercial_proposal'] > 0.7:
    print("Это коммерческое предложение")
```

### Пример 3: Валидация данных
```python
validation = ocr.validate_extracted_data(text, tables)
if validation['overall_quality'] < 0.6:
    print("Качество низкое, рекомендуется OCR")
    for issue in validation['issues']:
        print(f"- {issue}")
```

## 🚨 Устранение неполадок

### Проблема: OCR не инициализируется
**Решение:**
```bash
pip install easyocr opencv-python pymupdf
```

### Проблема: Медленная работа
**Решение:**
- Отключите OCR для простых документов
- Используйте `enable_ocr_fallback=False`
- Оптимизируйте размер изображений

### Проблема: Плохое качество распознавания
**Решение:**
- Проверьте качество исходного PDF
- Настройте языки OCR
- Увеличьте порог уверенности

## 🔮 Планы развития

### Версия 2.0:
- [ ] Поддержка GPU для ускорения
- [ ] Дополнительные языки
- [ ] Улучшенная предобработка
- [ ] Машинное обучение для классификации

### Версия 2.1:
- [ ] Веб-интерфейс для настройки OCR
- [ ] Пакетная обработка
- [ ] Кэширование результатов
- [ ] API для внешних систем

## 📚 Дополнительные ресурсы

- [EasyOCR Documentation](https://github.com/JaidedAI/EasyOCR)
- [PyMuPDF Documentation](https://pymupdf.readthedocs.io/)
- [OpenCV Documentation](https://docs.opencv.org/)
- [PDF Parsing Best Practices](https://example.com)

## 🤝 Поддержка

При возникновении проблем:
1. Проверьте логи приложения
2. Запустите тесты: `python test_ocr.py`
3. Проверьте установку зависимостей
4. Создайте issue в репозитории

---

**OCR модуль значительно улучшает качество парсинга PDF документов! 🎉**
