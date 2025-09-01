#!/usr/bin/env python3
"""
PDF Parser Application - Main Entry Point
"""

import sys
import logging
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from app.gui.main_window import MainWindow
from app.utils.config import setup_logging, load_config
from app.db.database import init_database

def main():
    """Main application entry point"""
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting PDF Parser Application")
    
    # Load configuration
    config = load_config()
    
    # Initialize database
    init_database()
    
    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("PDF Parser")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("PDF Parser App")
    
    # Set application style
    app.setStyle("Fusion")
    
    # Create and show main window
    main_window = MainWindow(config)
    main_window.show()
    
    # Start event loop
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
