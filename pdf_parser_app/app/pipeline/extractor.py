"""
PDF text and table extraction module
"""

import logging
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
import pdfplumber
import pandas as pd

logger = logging.getLogger(__name__)

def extract_text_and_tables(pdf_path: str) -> Tuple[str, List[pd.DataFrame], Dict[str, Any]]:
    """
    Extract text and tables from PDF
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        Tuple of (full_text, tables_list, extraction_info)
    """
    pages_text = []
    tables = []
    extraction_info = {
        'page_count': 0,
        'total_chars': 0,
        'tables_found': 0,
        'errors': []
    }
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            extraction_info['page_count'] = len(pdf.pages)
            
            for page_num, page in enumerate(pdf.pages):
                try:
                    # Extract text
                    text = page.extract_text() or ""
                    pages_text.append(text)
                    extraction_info['total_chars'] += len(text)
                    
                    # Try to extract tables
                    page_tables = extract_tables_from_page(page, page_num)
                    tables.extend(page_tables)
                    
                except Exception as e:
                    error_msg = f"Error processing page {page_num + 1}: {e}"
                    logger.warning(error_msg)
                    extraction_info['errors'].append(error_msg)
                    continue
            
            extraction_info['tables_found'] = len(tables)
            
            # Combine all text
            full_text = "\n\n".join(pages_text)
            
            logger.info(f"Extracted {extraction_info['total_chars']} characters and {len(tables)} tables from {pdf_path}")
            
            return full_text, tables, extraction_info
            
    except Exception as e:
        error_msg = f"Failed to extract from PDF {pdf_path}: {e}"
        logger.error(error_msg)
        extraction_info['errors'].append(error_msg)
        return "", [], extraction_info

def extract_tables_from_page(page, page_num: int) -> List[pd.DataFrame]:
    """
    Extract tables from a single page
    
    Args:
        page: pdfplumber page object
        page_num: Page number for logging
        
    Returns:
        List of DataFrames
    """
    tables = []
    
    try:
        # Method 1: Try pdfplumber's built-in table extraction
        page_tables = page.extract_tables()
        
        for table_idx, table_data in enumerate(page_tables):
            if table_data and len(table_data) > 1:  # At least header + 1 row
                try:
                    # Convert to DataFrame
                    df = pd.DataFrame(table_data[1:], columns=table_data[0])
                    
                    # Basic validation - check if it looks like a table
                    if is_valid_table(df):
                        df['_page'] = page_num + 1
                        df['_table_id'] = table_idx + 1
                        tables.append(df)
                        logger.debug(f"Page {page_num + 1}, Table {table_idx + 1}: {len(df)} rows, {len(df.columns)} columns")
                    else:
                        logger.debug(f"Page {page_num + 1}, Table {table_idx + 1}: Rejected (invalid structure)")
                        
                except Exception as e:
                    logger.warning(f"Failed to process table {table_idx + 1} on page {page_num + 1}: {e}")
                    continue
        
        # Method 2: Try to find table-like structures by bounding boxes
        if not tables:
            bbox_tables = extract_tables_by_bbox(page)
            tables.extend(bbox_tables)
            
    except Exception as e:
        logger.warning(f"Error extracting tables from page {page_num + 1}: {e}")
    
    return tables

def extract_tables_by_bbox(page) -> List[pd.DataFrame]:
    """
    Extract tables by analyzing bounding boxes of text elements
    
    Args:
        page: pdfplumber page object
        
    Returns:
        List of DataFrames
    """
    tables = []
    
    try:
        # Get all text objects with their positions
        chars = page.chars
        
        if not chars:
            return tables
        
        # Group characters by lines (similar y-coordinates)
        lines = group_chars_by_lines(chars)
        
        # Try to identify table structure
        if len(lines) > 2:  # At least header + 2 data rows
            table_data = []
            
            for line in lines:
                # Sort characters in line by x-coordinate
                line_chars = sorted(line, key=lambda c: c['x0'])
                
                # Group characters into columns
                columns = group_chars_into_columns(line_chars)
                
                if columns:
                    table_data.append(columns)
            
            if len(table_data) > 1:
                try:
                    df = pd.DataFrame(table_data[1:], columns=table_data[0])
                    if is_valid_table(df):
                        tables.append(df)
                except Exception:
                    pass
                    
    except Exception as e:
        logger.debug(f"BBox table extraction failed: {e}")
    
    return tables

def group_chars_by_lines(chars: List[Dict]) -> List[List[Dict]]:
    """Group characters by their y-coordinate (lines)"""
    if not chars:
        return []
    
    # Sort by y-coordinate
    sorted_chars = sorted(chars, key=lambda c: c['y0'], reverse=True)
    
    lines = []
    current_line = []
    current_y = None
    tolerance = 5  # pixels
    
    for char in sorted_chars:
        if current_y is None:
            current_y = char['y0']
            current_line.append(char)
        elif abs(char['y0'] - current_y) <= tolerance:
            current_line.append(char)
        else:
            if current_line:
                lines.append(current_line)
            current_line = [char]
            current_y = char['y0']
    
    if current_line:
        lines.append(current_line)
    
    return lines

def group_chars_into_columns(chars: List[Dict]) -> List[str]:
    """Group characters in a line into columns"""
    if not chars:
        return []
    
    # Simple column detection based on x-coordinate gaps
    columns = []
    current_column = []
    prev_x = None
    
    for char in chars:
        if prev_x is None:
            current_column.append(char['text'])
            prev_x = char['x1']
        elif char['x0'] - prev_x > 20:  # Gap threshold
            if current_column:
                columns.append(''.join(current_column).strip())
                current_column = []
            current_column.append(char['text'])
            prev_x = char['x1']
        else:
            current_column.append(char['text'])
            prev_x = char['x1']
    
    if current_column:
        columns.append(''.join(current_column).strip())
    
    return columns

def is_valid_table(df: pd.DataFrame) -> bool:
    """
    Check if DataFrame looks like a valid table
    
    Args:
        df: DataFrame to validate
        
    Returns:
        True if valid table structure
    """
    if df.empty:
        return False
    
    # Check minimum dimensions
    if len(df) < 1 or len(df.columns) < 2:
        return False
    
    # Check if columns have meaningful names (not empty)
    non_empty_cols = [col for col in df.columns if col and str(col).strip()]
    if len(non_empty_cols) < 2:
        return False
    
    # Check if data looks structured (not all empty)
    non_empty_rows = df.dropna(how='all')
    if len(non_empty_rows) < 1:
        return False
    
    return True
