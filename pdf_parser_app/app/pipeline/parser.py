"""
Text parsing module for extracting structured data from PDF text
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd

logger = logging.getLogger(__name__)

# Common column header patterns (Russian and English)
COLUMN_PATTERNS = {
    'name': [
        'наименование', 'название', 'товар', 'описание', 'name', 'description', 'item', 'product'
    ],
    'qty': [
        'количество', 'кол-во', 'кол', 'qty', 'quantity', 'amount', 'шт'
    ],
    'unit': [
        'единица', 'ед.изм', 'ед', 'unit', 'measure', 'измерение'
    ],
    'price': [
        'цена', 'стоимость', 'price', 'cost', 'rate'
    ],
    'currency': [
        'валюта', 'currency', 'curr', 'руб', 'usd', 'eur'
    ],
    'total': [
        'сумма', 'итого', 'total', 'sum', 'amount'
    ]
}

# Common unit patterns
UNIT_PATTERNS = [
    r'шт', r'кг', r'м', r'л', r'pcs', r'kg', r'm', r'l', r'шт\.', r'кг\.', r'м\.', r'л\.'
]

# Currency patterns
CURRENCY_PATTERNS = [
    r'руб', r'₽', r'usd', r'eur', r'руб\.', r'USD', r'EUR'
]

class TextParser:
    """Parser for extracting structured data from text"""
    
    def __init__(self):
        self.line_patterns = self._compile_patterns()
    
    def _compile_patterns(self) -> List[re.Pattern]:
        """Compile regex patterns for line parsing"""
        patterns = [
            # Pattern 1: name + qty + unit + price + currency
            re.compile(
                r'(?P<name>.+?)\s+(?P<qty>[\d\s\.,]+)\s*(?P<unit>шт|кг|м|л|pcs|kg|m|l|шт\.|кг\.|м\.|л\.)?\s+'
                r'(?P<price>[\d\s\.,]+)\s*(?P<currency>руб|₽|USD|EUR|руб\.|usd|eur)?',
                re.IGNORECASE | re.MULTILINE
            ),
            
            # Pattern 2: name + price + qty + unit
            re.compile(
                r'(?P<name>.+?)\s+(?P<price>[\d\s\.,]+)\s*(?P<currency>руб|₽|USD|EUR|руб\.|usd|eur)?\s+'
                r'(?P<qty>[\d\s\.,]+)\s*(?P<unit>шт|кг|м|л|pcs|kg|m|l|шт\.|кг\.|м\.|л\.)?',
                re.IGNORECASE | re.MULTILINE
            ),
            
            # Pattern 3: simple name + numbers (fallback)
            re.compile(
                r'(?P<name>.+?)\s+(?P<qty>[\d\s\.,]+)\s+(?P<price>[\d\s\.,]+)',
                re.IGNORECASE | re.MULTILINE
            )
        ]
        return patterns
    
    def parse_text_to_items(self, text: str, tables: List[pd.DataFrame] = None) -> List[Dict[str, Any]]:
        """
        Parse text and tables to extract items
        
        Args:
            text: Raw text from PDF
            tables: List of extracted tables
            
        Returns:
            List of parsed items
        """
        items = []
        
        # First try to parse tables if available
        if tables:
            table_items = self._parse_tables(tables)
            items.extend(table_items)
            logger.info(f"Parsed {len(table_items)} items from tables")
        
        # Then try to parse text lines
        if text:
            text_items = self._parse_text_lines(text)
            items.extend(text_items)
            logger.info(f"Parsed {len(text_items)} items from text")
        
        # Remove duplicates and validate
        unique_items = self._deduplicate_items(items)
        valid_items = [item for item in unique_items if self._validate_item(item)]
        
        logger.info(f"Total valid items: {len(valid_items)}")
        return valid_items
    
    def _parse_tables(self, tables: List[pd.DataFrame]) -> List[Dict[str, Any]]:
        """Parse items from table DataFrames"""
        items = []
        
        for table_idx, table in enumerate(tables):
            try:
                # Try to identify column mapping
                column_mapping = self._identify_columns(table.columns)
                
                if column_mapping:
                    # Parse table rows using column mapping
                    table_items = self._parse_table_with_mapping(table, column_mapping, table_idx)
                    items.extend(table_items)
                else:
                    # Fallback: try to parse each row as text
                    table_items = self._parse_table_fallback(table, table_idx)
                    items.extend(table_items)
                    
            except Exception as e:
                logger.warning(f"Failed to parse table {table_idx}: {e}")
                continue
        
        return items
    
    def _identify_columns(self, columns: pd.Index) -> Optional[Dict[str, int]]:
        """Identify column mapping based on header patterns"""
        mapping = {}
        
        for col_idx, col_name in enumerate(columns):
            col_name_str = str(col_name).lower().strip()
            
            for field, patterns in COLUMN_PATTERNS.items():
                for pattern in patterns:
                    if pattern.lower() in col_name_str:
                        mapping[field] = col_idx
                        break
                if field in mapping:
                    break
        
        # Check if we have at least name and one numeric field
        if 'name' in mapping and len(mapping) >= 2:
            return mapping
        
        return None
    
    def _parse_table_with_mapping(self, table: pd.DataFrame, mapping: Dict[str, int], table_idx: int) -> List[Dict[str, Any]]:
        """Parse table using identified column mapping"""
        items = []
        
        for row_idx, row in table.iterrows():
            try:
                item = {
                    'name': str(row.iloc[mapping.get('name', 0)]) if 'name' in mapping else '',
                    'qty': self._parse_number(row.iloc[mapping.get('qty', 1)]) if 'qty' in mapping else 1.0,
                    'unit': str(row.iloc[mapping.get('unit', 2)]) if 'unit' in mapping else '',
                    'price': self._parse_number(row.iloc[mapping.get('price', 3)]) if 'price' in mapping else 0.0,
                    'currency': str(row.iloc[mapping.get('currency', 4)]) if 'currency' in mapping else 'RUB',
                    'total': self._parse_number(row.iloc[mapping.get('total', 5)]) if 'total' in mapping else None,
                    'source': f'table_{table_idx}_row_{row_idx}',
                    'confidence': 0.9  # High confidence for structured tables
                }
                
                # Calculate total if not provided
                if item['total'] is None and item['qty'] and item['price']:
                    item['total'] = item['qty'] * item['price']
                
                items.append(item)
                
            except Exception as e:
                logger.debug(f"Failed to parse table row {row_idx}: {e}")
                continue
        
        return items
    
    def _parse_table_fallback(self, table: pd.DataFrame, table_idx: int) -> List[Dict[str, Any]]:
        """Fallback parsing for tables without clear column mapping"""
        items = []
        
        for row_idx, row in table.iterrows():
            # Convert row to text and parse
            row_text = ' '.join(str(cell) for cell in row if pd.notna(cell))
            
            if row_text.strip():
                parsed_item = self._parse_single_line(row_text)
                if parsed_item:
                    parsed_item['source'] = f'table_{table_idx}_row_{row_idx}'
                    parsed_item['confidence'] = 0.7  # Medium confidence for fallback
                    items.append(parsed_item)
        
        return items
    
    def _parse_text_lines(self, text: str) -> List[Dict[str, Any]]:
        """Parse text lines to extract items"""
        items = []
        lines = text.split('\n')
        
        for line_idx, line in enumerate(lines):
            line = line.strip()
            if not line or len(line) < 10:  # Skip short lines
                continue
            
            parsed_item = self._parse_single_line(line)
            if parsed_item:
                parsed_item['source'] = f'text_line_{line_idx}'
                parsed_item['confidence'] = 0.6  # Lower confidence for text parsing
                items.append(parsed_item)
        
        return items
    
    def _parse_single_line(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse a single line of text"""
        for pattern in self.line_patterns:
            match = pattern.search(line)
            if match:
                try:
                    item = {
                        'name': match.group('name').strip(),
                        'qty': self._parse_number(match.group('qty')),
                        'unit': match.group('unit') or '',
                        'price': self._parse_number(match.group('price')),
                        'currency': match.group('currency') or 'RUB',
                        'total': None,
                        'source': 'regex_match',
                        'confidence': 0.8
                    }
                    
                    # Calculate total
                    if item['qty'] and item['price']:
                        item['total'] = item['qty'] * item['price']
                    
                    # Validate item
                    if self._validate_item(item):
                        return item
                        
                except Exception as e:
                    logger.debug(f"Failed to parse line with pattern: {e}")
                    continue
        
        return None
    
    def _parse_number(self, value: Any) -> Optional[float]:
        """Parse number from various formats"""
        if pd.isna(value):
            return None
        
        try:
            if isinstance(value, (int, float)):
                return float(value)
            
            # Convert to string and clean
            value_str = str(value).strip()
            
            # Remove common non-numeric characters
            value_str = re.sub(r'[^\d\.,\s-]', '', value_str)
            
            # Handle different decimal separators
            if ',' in value_str and '.' in value_str:
                # Format: 1,234.56
                value_str = value_str.replace(',', '')
            elif ',' in value_str:
                # Format: 1,23 or 1 234,56
                if value_str.count(',') == 1 and len(value_str.split(',')[-1]) <= 2:
                    # Likely decimal separator
                    value_str = value_str.replace(',', '.')
                else:
                    # Likely thousands separator
                    value_str = value_str.replace(',', '')
            
            # Remove spaces
            value_str = value_str.replace(' ', '')
            
            return float(value_str) if value_str else None
            
        except (ValueError, TypeError):
            return None
    
    def _validate_item(self, item: Dict[str, Any]) -> bool:
        """Validate parsed item"""
        # Must have name
        if not item.get('name') or len(item['name'].strip()) < 2:
            return False
        
        # Must have quantity and price
        if item.get('qty') is None or item.get('price') is None:
            return False
        
        # Quantity and price must be positive
        if item['qty'] <= 0 or item['price'] <= 0:
            return False
        
        return True
    
    def _deduplicate_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate items based on name, qty, and price"""
        seen = set()
        unique_items = []
        
        for item in items:
            # Create key for deduplication
            key = (item.get('name', '').lower().strip(), 
                   item.get('qty'), 
                   item.get('price'))
            
            if key not in seen:
                seen.add(key)
                unique_items.append(item)
        
        return unique_items
