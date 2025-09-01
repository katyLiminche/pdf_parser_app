"""
PDF text layer detection module
"""

import logging
from pathlib import Path
from typing import Tuple, Optional
import pdfplumber

logger = logging.getLogger(__name__)

def detect_text_layer(pdf_path: str, min_text_length: int = 20) -> Tuple[bool, int, str]:
    """
    Detect if PDF has text layer and extract basic info
    
    Args:
        pdf_path: Path to PDF file
        min_text_length: Minimum text length to consider as having text layer
        
    Returns:
        Tuple of (has_text, total_chars, error_message)
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_chars = 0
            page_count = len(pdf.pages)
            
            for page_num, page in enumerate(pdf.pages):
                try:
                    text = page.extract_text()
                    if text:
                        text = text.strip()
                        total_chars += len(text)
                        logger.debug(f"Page {page_num + 1}: {len(text)} characters")
                except Exception as e:
                    logger.warning(f"Error extracting text from page {page_num + 1}: {e}")
                    continue
            
            has_text = total_chars >= min_text_length
            
            if has_text:
                logger.info(f"PDF has text layer: {total_chars} characters across {page_count} pages")
            else:
                logger.info(f"PDF appears to be scan/image: {total_chars} characters (below threshold {min_text_length})")
            
            return has_text, total_chars, ""
            
    except Exception as e:
        error_msg = f"Failed to analyze PDF {pdf_path}: {e}"
        logger.error(error_msg)
        return False, 0, error_msg

def get_pdf_info(pdf_path: str) -> dict:
    """
    Get basic PDF information
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        Dictionary with PDF info
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            info = {
                'page_count': len(pdf.pages),
                'metadata': pdf.metadata,
                'file_size': Path(pdf_path).stat().st_size,
                'has_text': False,
                'total_chars': 0
            }
            
            # Check text layer
            has_text, total_chars, _ = detect_text_layer(pdf_path)
            info['has_text'] = has_text
            info['total_chars'] = total_chars
            
            return info
            
    except Exception as e:
        logger.error(f"Failed to get PDF info for {pdf_path}: {e}")
        return {
            'page_count': 0,
            'metadata': {},
            'file_size': 0,
            'has_text': False,
            'total_chars': 0,
            'error': str(e)
        }
