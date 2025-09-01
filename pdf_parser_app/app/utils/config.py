"""
Configuration management for PDF Parser Application
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any
from dataclasses import dataclass, asdict

@dataclass
class AppConfig:
    """Application configuration"""
    # Excel template settings
    excel_template_path: str = ""
    excel_sheet_name: str = "Raw_imports"
    backup_folder: str = "backups"
    
    # Parsing settings
    fuzzy_threshold_auto: int = 90
    fuzzy_threshold_suggest: int = 70
    min_text_length: int = 20
    
    # File monitoring
    inbox_folder: str = "inbox"
    supported_extensions: tuple = (".pdf",)
    
    # Database
    database_path: str = "data/pdf_parser.db"
    
    # Logging
    log_level: str = "INFO"
    log_file: str = "logs/app.log"

def get_default_config_path() -> Path:
    """Get default configuration file path"""
    return Path.home() / ".pdf_parser" / "config.json"

def load_config(config_path: str = None) -> AppConfig:
    """Load configuration from file or create default"""
    if config_path is None:
        config_path = get_default_config_path()
    
    config_path = Path(config_path)
    
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                return AppConfig(**config_data)
        except Exception as e:
            logging.warning(f"Failed to load config from {config_path}: {e}")
    
    # Return default config
    config = AppConfig()
    
    # Ensure config directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Save default config
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(asdict(config), f, indent=2, ensure_ascii=False)
    except Exception as e:
        logging.warning(f"Failed to save default config: {e}")
    
    return config

def save_config(config: AppConfig, config_path: str = None) -> bool:
    """Save configuration to file"""
    if config_path is None:
        config_path = get_default_config_path()
    
    try:
        config_path = Path(config_path)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(asdict(config), f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logging.error(f"Failed to save config: {e}")
        return False

def setup_logging(config: AppConfig = None):
    """Setup application logging"""
    if config is None:
        config = AppConfig()
    
    # Create logs directory
    log_path = Path(config.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_path, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
