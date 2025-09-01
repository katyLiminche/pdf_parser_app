"""
Main application window with OCR support
"""

import logging
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTabWidget, QTableWidget, QTableWidgetItem, QTextEdit,
    QPushButton, QLabel, QFileDialog, QMessageBox, QProgressBar,
    QStatusBar, QMenuBar, QMenu, QListWidget, QListWidgetItem,
    QGroupBox, QGridLayout, QHeaderView, QAbstractItemView,
    QCheckBox, QFrame, QScrollArea
)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QMimeData
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QFont, QIcon

from app.utils.config import AppConfig
from app.pipeline.ingest import FileIngester, DragDropHandler
from app.pipeline.detector import detect_text_layer
from app.pipeline.extractor import extract_text_and_tables
from app.pipeline.competitive_parser import CompetitiveParser
from app.pipeline.matcher import ProductMatcher
from app.pipeline.writer import ExcelWriter
from app.db.database import get_db_session
from app.db.models import Document, Item, Supplier
from app.pipeline.universal_parser import UniversalParser

logger = logging.getLogger(__name__)

class ProcessingThread(QThread):
    """Background thread for PDF processing with OCR support"""
    
    progress = Signal(int)
    finished = Signal(dict)
    error = Signal(str)
    ocr_status = Signal(str)
    
    def __init__(self, pdf_path: str, config: AppConfig, use_ocr: bool = True):
        super().__init__()
        self.pdf_path = pdf_path
        self.config = config
        self.use_ocr = use_ocr
    
    def run(self):
        """Process PDF file with optional OCR"""
        try:
            self.progress.emit(5)
            self.ocr_status.emit("Инициализация...")
            
            # Initialize parser with OCR support
            parser = UniversalParser(use_ocr=self.use_ocr)
            
            if self.use_ocr:
                self.ocr_status.emit("OCR включен - улучшенная обработка")
            else:
                self.ocr_status.emit("OCR отключен - стандартная обработка")
            
            self.progress.emit(15)
            
            # Use new parse_pdf_file method with OCR support
            result = parser.parse_pdf_file(self.pdf_path, enable_ocr=self.use_ocr)
            
            if 'error' in result:
                self.error.emit(result['error'])
                return
            
            self.progress.emit(50)
            
            # Extract items from result
            items = result.get('best_items', [])
            
            if not items:
                self.error.emit("Не удалось извлечь товарные позиции из PDF")
                return
            
            # Add parser information to items
            for item in items:
                item['parser_used'] = result.get('best_parser', 'unknown')
                item['supplier_name'] = result.get('parser_results', {}).get('supplier_profile_parser', {}).get('supplier_name', 'Unknown')
            
            self.progress.emit(70)
            
            # Match with products
            matcher = ProductMatcher(
                auto_threshold=self.config.fuzzy_threshold_auto,
                suggest_threshold=self.config.fuzzy_threshold_suggest
            )
            matched_items = matcher.batch_match_items(items)
            
            self.progress.emit(90)
            
            # Prepare result with OCR information
            result.update({
                'items': matched_items,
                'ocr_used': result.get('ocr_info', {}).get('ocr_additions', 0) > 0,
                'extraction_quality': result.get('extraction_quality', {}),
                'document_type': result.get('document_type', {}),
                'processing_method': 'enhanced_with_ocr' if self.use_ocr else 'standard'
            })
            
            self.progress.emit(100)
            self.ocr_status.emit("Обработка завершена")
            self.finished.emit(result)
            
        except Exception as e:
            error_msg = f"Ошибка обработки PDF: {e}"
            logger.error(error_msg)
            self.error.emit(error_msg)

class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self.current_document = None
        self.current_items = []
        
        # Initialize components
        self.file_ingester = FileIngester(config)
        self.drag_drop_handler = DragDropHandler(self.on_file_dropped)
        self.parser = UniversalParser()
        self.matcher = ProductMatcher(
            auto_threshold=config.fuzzy_threshold_auto,
            suggest_threshold=config.fuzzy_threshold_suggest
        )
        self.excel_writer = ExcelWriter(config.backup_folder)
        
        self.setup_ui()
        self.setup_menu()
        self.setup_status_bar()
        
        # Start file monitoring
        self.file_ingester.start_monitoring(self.on_file_added)
        
        # Scan existing files
        self.file_ingester.scan_existing_files(self.on_file_added)
        
        logger.info("Main window initialized")

    def setup_ui(self):
        """Setup user interface"""
        self.setWindowTitle("PDF Parser Application")
        self.setGeometry(100, 100, 1200, 800)
        
        # Enable drag and drop
        self.setAcceptDrops(True)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QHBoxLayout(central_widget)
        
        # Create splitter
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # Left panel - File list
        self.setup_left_panel(splitter)
        
        # Right panel - Preview and editing
        self.setup_right_panel(splitter)
        
        # Set splitter proportions
        splitter.setSizes([300, 900])
    
    def setup_left_panel(self, parent):
        """Setup left panel with file list"""
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # Title
        title_label = QLabel("Documents")
        title_label.setFont(QFont("Arial", 12, QFont.Bold))
        left_layout.addWidget(title_label)
        
        # File list
        self.file_list = QListWidget()
        self.file_list.itemClicked.connect(self.on_file_selected)
        left_layout.addWidget(self.file_list)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        add_button = QPushButton("Add Files")
        add_button.clicked.connect(self.add_files)
        button_layout.addWidget(add_button)
        
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh_file_list)
        button_layout.addWidget(refresh_button)
        
        left_layout.addLayout(button_layout)
        
        # OCR Control Panel
        self.setup_ocr_panel(left_layout)
        
        parent.addWidget(left_widget)
    
    def setup_ocr_panel(self, parent_layout):
        """Setup OCR control panel"""
        ocr_group = QGroupBox("🔍 OCR Настройки")
        ocr_layout = QVBoxLayout(ocr_group)
        
        # OCR Status
        self.ocr_status_label = QLabel("OCR: Инициализация...")
        self.ocr_status_label.setStyleSheet("color: gray; font-weight: bold;")
        ocr_layout.addWidget(self.ocr_status_label)
        
        # OCR Toggle
        self.ocr_checkbox = QCheckBox("Использовать OCR")
        self.ocr_checkbox.setChecked(True)
        self.ocr_checkbox.stateChanged.connect(self.on_ocr_toggled)
        ocr_layout.addWidget(self.ocr_checkbox)
        
        # OCR Info
        self.ocr_info_label = QLabel("OCR улучшает качество парсинга")
        self.ocr_info_label.setStyleSheet("color: blue; font-size: 10px;")
        self.ocr_info_label.setWordWrap(True)
        ocr_layout.addWidget(self.ocr_info_label)
        
        # OCR Languages
        languages_layout = QHBoxLayout()
        languages_layout.addWidget(QLabel("Языки:"))
        self.ru_lang_checkbox = QCheckBox("RU")
        self.ru_lang_checkbox.setChecked(True)
        self.en_lang_checkbox = QCheckBox("EN")
        self.en_lang_checkbox.setChecked(True)
        languages_layout.addWidget(self.ru_lang_checkbox)
        languages_layout.addWidget(self.en_lang_checkbox)
        ocr_layout.addLayout(languages_layout)
        
        # OCR Test Button
        test_ocr_button = QPushButton("Тест OCR")
        test_ocr_button.clicked.connect(self.test_ocr_functionality)
        test_ocr_button.setStyleSheet("background-color: #4CAF50; color: white;")
        ocr_layout.addWidget(test_ocr_button)
        
        parent_layout.addWidget(ocr_group)
    
    def setup_right_panel(self, parent):
        """Setup right panel with tabs"""
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # Tab widget
        self.tab_widget = QTabWidget()
        right_layout.addWidget(self.tab_widget)
        
        # Raw Text tab
        self.setup_raw_text_tab()
        
        # Parsed Table tab
        self.setup_parsed_table_tab()
        
        # Document Info tab
        self.setup_document_info_tab()
        
        # Bottom buttons
        self.setup_bottom_buttons(right_layout)
        
        parent.addWidget(right_widget)
    
    def setup_raw_text_tab(self):
        """Setup raw text preview tab"""
        text_widget = QWidget()
        text_layout = QVBoxLayout(text_widget)
        
        # Text display
        self.raw_text_display = QTextEdit()
        self.raw_text_display.setReadOnly(True)
        self.raw_text_display.setFont(QFont("Courier", 10))
        text_layout.addWidget(self.raw_text_display)
        
        self.tab_widget.addTab(text_widget, "Raw Text")
    
    def setup_parsed_table_tab(self):
        """Setup parsed table editing tab"""
        table_widget = QWidget()
        table_layout = QVBoxLayout(table_widget)
        
        # Table
        self.items_table = QTableWidget()
        self.items_table.setColumnCount(10)
        self.items_table.setHorizontalHeaderLabels([
            "Supplier", "Name", "Qty", "Unit", "Price", 
            "Currency", "Total", "SKU", "Source", "Confidence"
        ])
        
        # Table properties
        self.items_table.setAlternatingRowColors(True)
        self.items_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.items_table.horizontalHeader().setStretchLastSection(True)
        self.items_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        
        table_layout.addWidget(self.items_table)
        
        # Table buttons
        table_button_layout = QHBoxLayout()
        
        edit_button = QPushButton("Edit Cell")
        edit_button.clicked.connect(self.edit_selected_cell)
        table_button_layout.addWidget(edit_button)
        
        accept_selected_button = QPushButton("Accept Selected")
        accept_selected_button.clicked.connect(self.accept_selected_items)
        table_button_layout.addWidget(accept_selected_button)
        
        accept_all_button = QPushButton("Accept All")
        accept_all_button.clicked.connect(self.accept_all_items)
        table_button_layout.addWidget(accept_all_button)
        
        table_layout.addLayout(table_button_layout)
        
        self.tab_widget.addTab(table_widget, "Parsed Table")
    
    def setup_document_info_tab(self):
        """Setup document information tab"""
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        
        # Document info group
        doc_group = QGroupBox("Document Information")
        doc_layout = QGridLayout(doc_group)
        
        self.doc_info_labels = {}
        info_fields = [
            "Filename", "File Size", "Pages", "Text Layer", 
            "Total Characters", "Tables Found", "Items Parsed"
        ]
        
        for i, field in enumerate(info_fields):
            label = QLabel(f"{field}:")
            label.setFont(QFont("Arial", 10, QFont.Bold))
            value = QLabel("N/A")
            doc_layout.addWidget(label, i, 0)
            doc_layout.addWidget(value, i, 1)
            self.doc_info_labels[field] = value
        
        info_layout.addWidget(doc_group)
        
        # Processing status
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        info_layout.addWidget(self.progress_bar)
        
        # OCR Status
        self.ocr_status_label = QLabel("OCR статус: Неизвестно")
        self.ocr_status_label.setFont(QFont("Arial", 10))
        info_layout.addWidget(self.ocr_status_label)

        info_layout.addStretch()
        
        self.tab_widget.addTab(info_widget, "Document Info")
    
    def setup_bottom_buttons(self, parent_layout):
        """Setup bottom action buttons"""
        button_layout = QHBoxLayout()
        
        # OCR Toggle
        self.ocr_checkbox = QCheckBox("Использовать OCR для обработки")
        self.ocr_checkbox.setChecked(self.config.use_ocr)
        self.ocr_checkbox.stateChanged.connect(self.on_ocr_toggle)
        button_layout.addWidget(self.ocr_checkbox)

        # Export button
        self.export_button = QPushButton("Export to Excel")
        self.export_button.clicked.connect(self.export_to_excel)
        self.export_button.setEnabled(False)
        button_layout.addWidget(self.export_button)
        
        # Settings button
        settings_button = QPushButton("Settings")
        settings_button.clicked.connect(self.show_settings)
        button_layout.addWidget(settings_button)
        
        button_layout.addStretch()
        
        parent_layout.addLayout(button_layout)
    
    def setup_menu(self):
        """Setup application menu"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        add_action = QAction("Add Files", self)
        add_action.setShortcut("Ctrl+O")
        add_action.triggered.connect(self.add_files)
        file_menu.addAction(add_action)
        
        export_action = QAction("Export to Excel", self)
        export_action.setShortcut("Ctrl+E")
        export_action.triggered.connect(self.export_to_excel)
        file_menu.addAction(export_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Settings menu
        settings_menu = menubar.addMenu("Settings")
        
        config_action = QAction("Configuration", self)
        config_action.triggered.connect(self.show_settings)
        settings_menu.addAction(config_action)
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def setup_status_bar(self):
        """Setup status bar"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        """Handle drag enter event"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event: QDropEvent):
        """Handle drop event"""
        urls = event.mimeData().urls()
        file_paths = [url.toLocalFile() for url in urls]
        
        # Filter PDF files
        pdf_files = [path for path in file_paths if Path(path).suffix.lower() == '.pdf']
        
        if pdf_files:
            self.drag_drop_handler.handle_drop(pdf_files)
            self.refresh_file_list()
        else:
            QMessageBox.warning(self, "Invalid Files", "Please drop PDF files only.")
    
    def on_file_dropped(self, file_path: str, file_info: Dict[str, Any]):
        """Handle dropped file"""
        self.add_file_to_list(file_path, file_info)
        self.process_pdf_file(file_path)
    
    def on_file_added(self, file_path: str, file_info: Dict[str, Any]):
        """Handle file added to inbox"""
        self.add_file_to_list(file_path, file_info)
    
    def add_file_to_list(self, file_path: str, file_info: Dict[str, Any]):
        """Add file to file list"""
        filename = Path(file_path).name
        
        # Create list item
        item = QListWidgetItem()
        
        # Set status icon and text
        if file_info.get('has_text', False):
            item.setText(f"✓ {filename}")
            item.setData(Qt.UserRole, {'path': file_path, 'status': 'detected_text'})
        else:
            item.setText(f"✗ {filename}")
            item.setData(Qt.UserRole, {'path': file_path, 'status': 'no_text'})
        
        self.file_list.addItem(item)
        self.update_file_status()
    
    def on_file_selected(self, item: QListWidgetItem):
        """Handle file selection"""
        file_data = item.data(Qt.UserRole)
        if file_data:
            file_path = file_data['path']
            self.process_pdf_file(file_path)
    
    def process_pdf_file(self, pdf_path: str):
        """Process PDF file with OCR support"""
        self.current_document = pdf_path
        self.status_bar.showMessage(f"Обработка {Path(pdf_path).name}...")
        
        # Use new OCR-enabled processing method
        self.process_file_with_ocr(pdf_path)
    
    def on_processing_finished(self, result: Dict[str, Any]):
        """Handle processing completion"""
        self.progress_bar.setVisible(False)
        self.status_bar.showMessage("Processing completed")
        
        # Update document info
        self.update_document_info(result)
        
        # Update raw text display
        self.raw_text_display.setText(result.get('text', ''))
        
        # Update items table
        self.update_items_table(result.get('items', []))
        
        # Enable export
        self.export_button.setEnabled(True)
        
        logger.info(f"Processing completed for {result['pdf_path']}")
    
    def on_processing_error(self, error_msg: str):
        """Handle processing error"""
        self.progress_bar.setVisible(False)
        self.status_bar.showMessage("Processing failed")
        
        QMessageBox.critical(self, "Processing Error", f"Failed to process PDF:\n{error_msg}")
        logger.error(f"Processing error: {error_msg}")
    
    def update_document_info(self, result: Dict[str, Any]):
        """Update document information display"""
        pdf_path = Path(result['pdf_path'])
        extraction_info = result.get('extraction_info', {})
        
        info_updates = {
            "Filename": pdf_path.name,
            "File Size": f"{pdf_path.stat().st_size:,} bytes",
            "Pages": str(extraction_info.get('page_count', 'N/A')),
            "Text Layer": "Yes" if extraction_info.get('total_chars', 0) > 0 else "No",
            "Total Characters": str(extraction_info.get('total_chars', 'N/A')),
            "Tables Found": str(extraction_info.get('tables_found', 'N/A')),
            "Items Parsed": str(len(result.get('items', [])))
        }
        
        for field, value in info_updates.items():
            if field in self.doc_info_labels:
                self.doc_info_labels[field].setText(value)
    
    def update_items_table(self, items: List[Dict[str, Any]]):
        """Update items table with parsed data"""
        self.current_items = items
        
        # Clear table
        self.items_table.setRowCount(0)
        
        if not items:
            return
        
        # Set row count
        self.items_table.setRowCount(len(items))
        
        # Populate table
        for row, item in enumerate(items):
            # Supplier (placeholder)
            supplier_item = QTableWidgetItem(item.get('supplier', ''))
            self.items_table.setItem(row, 0, supplier_item)
            
            # Name
            name_item = QTableWidgetItem(item.get('name', ''))
            self.items_table.setItem(row, 1, name_item)
            
            # Quantity
            qty_item = QTableWidgetItem(str(item.get('qty', '')))
            self.items_table.setItem(row, 2, qty_item)
            
            # Unit
            unit_item = QTableWidgetItem(item.get('unit', ''))
            self.items_table.setItem(row, 3, unit_item)
            
            # Price
            price_item = QTableWidgetItem(str(item.get('price', '')))
            self.items_table.setItem(row, 4, price_item)
            
            # Currency
            currency_item = QTableWidgetItem(item.get('currency', ''))
            self.items_table.setItem(row, 5, currency_item)
            
            # Total
            total_item = QTableWidgetItem(str(item.get('total', '')))
            self.items_table.setItem(row, 6, total_item)
            
            # SKU
            sku_item = QTableWidgetItem(item.get('sku', item.get('sku_suggestion', '')))
            self.items_table.setItem(row, 7, sku_item)
            
            # Source
            source_item = QTableWidgetItem(item.get('source', ''))
            self.items_table.setItem(row, 8, source_item)
            
            # Confidence
            confidence = item.get('confidence_score', 0)
            confidence_item = QTableWidgetItem(f"{confidence:.2f}")
            self.items_table.setItem(row, 9, confidence_item)
            
            # Color code confidence
            if confidence >= 0.9:
                confidence_item.setBackground(Qt.green)
            elif confidence >= 0.7:
                confidence_item.setBackground(Qt.yellow)
            else:
                confidence_item.setBackground(Qt.red)
    
    def add_files(self):
        """Add files via file dialog"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "Select PDF Files", "", "PDF Files (*.pdf)"
        )
        
        if file_paths:
            for file_path in file_paths:
                self.file_ingester.add_file(file_path, move_to_inbox=True)
            
            self.refresh_file_list()
    
    def refresh_file_list(self):
        """Refresh file list"""
        self.file_list.clear()
        
        # Get inbox status
        status = self.file_ingester.get_inbox_status()
        
        for file_info in status.get('files', []):
            self.add_file_to_list(file_info['file_path'], file_info)
    
    def update_file_status(self):
        """Update file status display"""
        total_files = self.file_list.count()
        self.file_status_label.setText(f"{total_files} file(s)")
    
    def edit_selected_cell(self):
        """Edit selected table cell"""
        current_item = self.items_table.currentItem()
        if current_item:
            self.items_table.editItem(current_item)
    
    def accept_selected_items(self):
        """Accept selected items"""
        selected_rows = set(item.row() for item in self.items_table.selectedItems())
        
        if not selected_rows:
            QMessageBox.information(self, "No Selection", "Please select items to accept.")
            return
        
        # Mark selected items as accepted
        for row in selected_rows:
            # Update item status (could add visual indication)
            pass
        
        QMessageBox.information(self, "Items Accepted", f"Accepted {len(selected_rows)} items.")
    
    def accept_all_items(self):
        """Accept all items"""
        if not self.current_items:
            QMessageBox.information(self, "No Items", "No items to accept.")
            return
        
        # Mark all items as accepted
        QMessageBox.information(self, "All Items Accepted", f"Accepted all {len(self.current_items)} items.")
    
    def export_to_excel(self):
        """Export items to Excel"""
        if not self.current_items:
            QMessageBox.warning(self, "No Data", "No items to export.")
            return
        
        # Get template path
        template_path = self.config.excel_template_path
        if not template_path:
            template_path, _ = QFileDialog.getOpenFileName(
                self, "Select Excel Template", "", "Excel Files (*.xlsx *.xls)"
            )
            if not template_path:
                return
        
        # Get output path
        output_path, _ = QFileDialog.getSaveFileName(
            self, "Save Excel File", "", "Excel Files (*.xlsx)"
        )
        if not output_path:
            return
        
        try:
            # Export to Excel
            backup_path = self.excel_writer.write_to_template(
                template_path, output_path, self.current_items
            )
            
            if backup_path:
                QMessageBox.information(
                    self, "Export Successful", 
                    f"Exported {len(self.current_items)} items to Excel.\nBackup created: {backup_path}"
                )
            else:
                QMessageBox.information(
                    self, "Export Successful", 
                    f"Exported {len(self.current_items)} items to Excel."
                )
            
            self.status_bar.showMessage("Export completed")
            
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export: {e}")
            logger.error(f"Export error: {e}")
    
    def show_settings(self):
        """Show settings dialog"""
        QMessageBox.information(self, "Settings", "Settings dialog not implemented yet.")
    
    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self, "About PDF Parser",
            "PDF Parser Application v1.0.0\n\n"
            "A tool for parsing PDF documents and extracting structured data."
        )

    def on_ocr_toggle(self, state):
        """Handle OCR toggle state change"""
        self.config.use_ocr = state == Qt.Checked
        logger.info(f"OCR toggled to: {self.config.use_ocr}")

    def on_ocr_toggled(self, state):
        """Handle OCR checkbox toggle"""
        use_ocr = state == Qt.Checked
        self.parser.toggle_ocr(use_ocr)
        
        if use_ocr:
            self.ocr_status_label.setText("OCR: Включен")
            self.ocr_status_label.setStyleSheet("color: green; font-weight: bold;")
            self.ocr_info_label.setText("OCR включен - улучшенное качество парсинга")
        else:
            self.ocr_status_label.setText("OCR: Отключен")
            self.ocr_status_label.setStyleSheet("color: red; font-weight: bold;")
            self.ocr_info_label.setText("OCR отключен - стандартное качество")
    
    def test_ocr_functionality(self):
        """Test OCR functionality"""
        try:
            # Get OCR status
            status = self.parser.get_ocr_status()
            
            if status['status'] == 'active':
                QMessageBox.information(
                    self, 
                    "OCR Тест", 
                    f"OCR работает корректно!\n"
                    f"Статус: {status['status']}\n"
                    f"Языки: {', '.join(status['languages'])}\n"
                    f"Enhanced Extractor: {'Доступен' if status['enhanced_extractor_available'] else 'Недоступен'}"
                )
            else:
                QMessageBox.warning(
                    self, 
                    "OCR Тест", 
                    f"OCR не активен!\n"
                    f"Статус: {status['status']}\n"
                    f"Проверьте установку зависимостей"
                )
                
        except Exception as e:
            QMessageBox.critical(
                self, 
                "OCR Ошибка", 
                f"Ошибка тестирования OCR:\n{str(e)}"
            )
    
    def update_ocr_status(self, status_text: str):
        """Update OCR status display"""
        self.ocr_status_label.setText(f"OCR: {status_text}")
    
    def get_ocr_languages(self) -> List[str]:
        """Get selected OCR languages"""
        languages = []
        if self.ru_lang_checkbox.isChecked():
            languages.append('ru')
        if self.en_lang_checkbox.isChecked():
            languages.append('en')
        return languages if languages else ['ru', 'en']
    
    def process_file_with_ocr(self, file_path: str):
        """Process file with OCR support"""
        try:
            # Get OCR settings
            use_ocr = self.ocr_checkbox.isChecked()
            languages = self.get_ocr_languages()
            
            # Create processing thread
            self.processing_thread = ProcessingThread(
                file_path, 
                self.config, 
                use_ocr=use_ocr
            )
            
            # Connect signals
            self.processing_thread.progress.connect(self.update_progress)
            self.processing_thread.finished.connect(self.on_processing_finished)
            self.processing_thread.error.connect(self.on_processing_error)
            self.processing_thread.ocr_status.connect(self.update_ocr_status)
            
            # Start processing
            self.processing_thread.start()
            
        except Exception as e:
            QMessageBox.critical(self, "Processing Error", f"Failed to start processing: {e}")
    
    def on_processing_finished(self, result: Dict[str, Any]):
        """Handle processing completion"""
        try:
            # Update current document and items
            self.current_document = result.get('pdf_path', '')
            self.current_items = result.get('items', [])
            
            # Display results
            self.display_items(self.current_items)
            
            # Show OCR information if used
            if result.get('ocr_used', False):
                ocr_info = result.get('ocr_info', {})
                QMessageBox.information(
                    self, 
                    "OCR Улучшения", 
                    f"OCR улучшил обработку документа!\n"
                    f"Добавлено текстовых блоков: {ocr_info.get('ocr_additions', 0)}\n"
                    f"Общее качество: {result.get('extraction_quality', {}).get('overall', 0):.1%}"
                )
            
            # Show quality assessment
            quality = result.get('extraction_quality', {})
            if quality:
                self.show_quality_report(quality)
                
        except Exception as e:
            logger.error(f"Error handling processing completion: {e}")
            QMessageBox.critical(self, "Error", f"Failed to handle results: {e}")
    
    def show_quality_report(self, quality: Dict[str, Any]):
        """Show quality assessment report"""
        report = f"📊 Отчет о качестве извлечения:\n\n"
        report += f"Общее качество: {quality.get('overall', 0):.1%}\n"
        report += f"Качество текста: {quality.get('text_quality', 0):.1%}\n"
        report += f"Качество таблиц: {quality.get('table_quality', 0):.1%}\n\n"
        
        issues = quality.get('issues', [])
        if issues:
            report += "⚠️ Проблемы:\n"
            for issue in issues:
                report += f"• {issue}\n"
        
        recommendations = quality.get('recommendations', [])
        if recommendations:
            report += "\n💡 Рекомендации:\n"
            for rec in recommendations:
                report += f"• {rec}\n"
        
        QMessageBox.information(self, "Отчет о качестве", report)
