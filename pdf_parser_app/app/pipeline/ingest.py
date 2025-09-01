"""
File ingestion and monitoring module
"""

import logging
import time
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import shutil

from app.pipeline.detector import detect_text_layer, get_pdf_info
from app.utils.config import AppConfig

logger = logging.getLogger(__name__)

class PDFFileHandler(FileSystemEventHandler):
    """Handler for PDF file events"""
    
    def __init__(self, callback: Callable[[str, Dict[str, Any]], None]):
        self.callback = callback
        self.processed_files = set()
    
    def on_created(self, event):
        """Handle file creation events"""
        if not event.is_directory and event.src_path.lower().endswith('.pdf'):
            self._process_file(event.src_path)
    
    def on_moved(self, event):
        """Handle file move events"""
        if not event.is_directory and event.src_path.lower().endswith('.pdf'):
            self._process_file(event.src_path)
    
    def _process_file(self, file_path: str):
        """Process a PDF file"""
        if file_path in self.processed_files:
            return
        
        try:
            logger.info(f"Processing new PDF file: {file_path}")
            
            # Get file info
            file_info = get_pdf_info(file_path)
            
            # Add file metadata
            file_info['file_path'] = file_path
            file_info['filename'] = Path(file_path).name
            file_info['timestamp'] = time.time()
            
            # Mark as processed
            self.processed_files.add(file_path)
            
            # Call callback
            self.callback(file_path, file_info)
            
        except Exception as e:
            logger.error(f"Failed to process file {file_path}: {e}")

class FileIngester:
    """File ingestion and monitoring"""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.observer = None
        self.handler = None
        self.is_monitoring = False
        
        # Ensure inbox folder exists
        self.inbox_path = Path(config.inbox_folder)
        self.inbox_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"File ingester initialized with inbox: {self.inbox_path}")
    
    def start_monitoring(self, callback: Callable[[str, Dict[str, Any]], None]):
        """Start monitoring inbox folder for new files"""
        if self.is_monitoring:
            logger.warning("File monitoring already active")
            return
        
        try:
            # Create handler
            self.handler = PDFFileHandler(callback)
            
            # Create observer
            self.observer = Observer()
            self.observer.schedule(self.handler, str(self.inbox_path), recursive=False)
            
            # Start monitoring
            self.observer.start()
            self.is_monitoring = True
            
            logger.info(f"Started monitoring folder: {self.inbox_path}")
            
        except Exception as e:
            logger.error(f"Failed to start file monitoring: {e}")
            raise
    
    def stop_monitoring(self):
        """Stop monitoring inbox folder"""
        if not self.is_monitoring:
            return
        
        try:
            if self.observer:
                self.observer.stop()
                self.observer.join()
                self.observer = None
            
            self.is_monitoring = False
            logger.info("Stopped file monitoring")
            
        except Exception as e:
            logger.error(f"Error stopping file monitoring: {e}")
    
    def scan_existing_files(self, callback: Callable[[str, Dict[str, Any]], None]):
        """Scan inbox folder for existing PDF files"""
        try:
            pdf_files = list(self.inbox_path.glob("*.pdf"))
            logger.info(f"Found {len(pdf_files)} existing PDF files in inbox")
            
            for pdf_file in pdf_files:
                try:
                    file_info = get_pdf_info(str(pdf_file))
                    file_info['file_path'] = str(pdf_file)
                    file_info['filename'] = pdf_file.name
                    file_info['timestamp'] = time.time()
                    
                    callback(str(pdf_file), file_info)
                    
                except Exception as e:
                    logger.error(f"Failed to process existing file {pdf_file}: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Failed to scan existing files: {e}")
    
    def add_file(self, file_path: str, move_to_inbox: bool = True) -> bool:
        """
        Add a PDF file to processing queue
        
        Args:
            file_path: Path to PDF file
            move_to_inbox: Whether to move file to inbox folder
            
        Returns:
            True if successful
        """
        try:
            source_path = Path(file_path)
            if not source_path.exists():
                logger.error(f"Source file not found: {file_path}")
                return False
            
            if not source_path.suffix.lower() == '.pdf':
                logger.error(f"File is not a PDF: {file_path}")
                return False
            
            if move_to_inbox:
                # Move file to inbox
                target_path = self.inbox_path / source_path.name
                
                # Handle duplicate names
                counter = 1
                while target_path.exists():
                    name = source_path.stem
                    suffix = source_path.suffix
                    target_path = self.inbox_path / f"{name}_{counter}{suffix}"
                    counter += 1
                
                shutil.move(str(source_path), str(target_path))
                logger.info(f"Moved file to inbox: {target_path}")
                return True
            else:
                # Process file in place
                logger.info(f"Processing file in place: {file_path}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to add file {file_path}: {e}")
            return False
    
    def get_inbox_status(self) -> Dict[str, Any]:
        """Get status of inbox folder"""
        try:
            pdf_files = list(self.inbox_path.glob("*.pdf"))
            
            status = {
                'inbox_path': str(self.inbox_path),
                'total_files': len(pdf_files),
                'is_monitoring': self.is_monitoring,
                'files': []
            }
            
            for pdf_file in pdf_files:
                try:
                    file_info = get_pdf_info(str(pdf_file))
                    file_info['filename'] = pdf_file.name
                    file_info['file_size'] = pdf_file.stat().st_size
                    file_info['modified_time'] = pdf_file.stat().st_mtime
                    
                    status['files'].append(file_info)
                    
                except Exception as e:
                    logger.debug(f"Failed to get info for {pdf_file}: {e}")
                    continue
            
            return status
            
        except Exception as e:
            logger.error(f"Failed to get inbox status: {e}")
            return {'error': str(e)}
    
    def cleanup_processed_files(self, processed_files: List[str], delete: bool = False):
        """
        Clean up processed files
        
        Args:
            processed_files: List of processed file paths
            delete: Whether to delete files (False = move to processed folder)
        """
        processed_folder = self.inbox_path / "processed"
        processed_folder.mkdir(exist_ok=True)
        
        for file_path in processed_files:
            try:
                source_path = Path(file_path)
                if not source_path.exists():
                    continue
                
                if delete:
                    source_path.unlink()
                    logger.info(f"Deleted processed file: {file_path}")
                else:
                    # Move to processed folder
                    target_path = processed_folder / source_path.name
                    
                    # Handle duplicate names
                    counter = 1
                    while target_path.exists():
                        name = source_path.stem
                        suffix = source_path.suffix
                        target_path = processed_folder / f"{name}_{counter}{suffix}"
                        counter += 1
                    
                    shutil.move(str(source_path), str(target_path))
                    logger.info(f"Moved to processed folder: {target_path}")
                    
            except Exception as e:
                logger.error(f"Failed to cleanup file {file_path}: {e}")
                continue

class DragDropHandler:
    """Handle drag and drop operations"""
    
    def __init__(self, callback: Callable[[str, Dict[str, Any]], None]):
        self.callback = callback
    
    def handle_drop(self, file_paths: List[str]) -> List[bool]:
        """
        Handle dropped files
        
        Args:
            file_paths: List of dropped file paths
            
        Returns:
            List of success status for each file
        """
        results = []
        
        for file_path in file_paths:
            try:
                file_path = Path(file_path)
                
                if not file_path.exists():
                    logger.warning(f"Dropped file not found: {file_path}")
                    results.append(False)
                    continue
                
                if file_path.suffix.lower() != '.pdf':
                    logger.warning(f"Dropped file is not a PDF: {file_path}")
                    results.append(False)
                    continue
                
                # Get file info
                file_info = get_pdf_info(str(file_path))
                file_info['file_path'] = str(file_path)
                file_info['filename'] = file_path.name
                file_info['timestamp'] = time.time()
                
                # Call callback
                self.callback(str(file_path), file_info)
                results.append(True)
                
                logger.info(f"Successfully processed dropped file: {file_path}")
                
            except Exception as e:
                logger.error(f"Failed to process dropped file {file_path}: {e}")
                results.append(False)
        
        return results
