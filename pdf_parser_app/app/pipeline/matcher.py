"""
Fuzzy matching module for SKU/product matching
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from rapidfuzz import process, fuzz
from sqlalchemy.orm import Session

from app.db.models import Product
from app.db.database import get_db_session

logger = logging.getLogger(__name__)

class ProductMatcher:
    """Fuzzy matching for products/SKUs"""
    
    def __init__(self, auto_threshold: float = 90.0, suggest_threshold: float = 70.0):
        self.auto_threshold = auto_threshold
        self.suggest_threshold = suggest_threshold
        self._product_cache = None
        self._cache_timestamp = None
    
    def get_product_cache(self) -> List[Tuple[str, str, int]]:
        """Get cached list of (name, sku, id) tuples"""
        # TODO: Implement proper caching with invalidation
        if self._product_cache is None:
            try:
                db = get_db_session()
                products = db.query(Product).all()
                self._product_cache = [(p.name, p.sku, p.id) for p in products]
                db.close()
                logger.debug(f"Cached {len(self._product_cache)} products")
            except Exception as e:
                logger.error(f"Failed to load product cache: {e}")
                self._product_cache = []
        
        return self._product_cache
    
    def find_matches(self, item_name: str, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Find fuzzy matches for item name
        
        Args:
            item_name: Name to search for
            limit: Maximum number of results
            
        Returns:
            List of match dictionaries
        """
        if not item_name or len(item_name.strip()) < 2:
            return []
        
        try:
            # Get product cache
            products = self.get_product_cache()
            if not products:
                return []
            
            # Extract names for matching
            product_names = [p[0] for p in products]
            
            # Perform fuzzy matching
            matches = process.extract(
                item_name, 
                product_names, 
                scorer=fuzz.WRatio, 
                limit=limit
            )
            
            # Convert to result format
            results = []
            for match_name, score, idx in matches:
                if score >= self.suggest_threshold:
                    product = products[idx]
                    results.append({
                        'name': product[0],
                        'sku': product[1],
                        'product_id': product[2],
                        'score': score,
                        'is_auto_match': score >= self.auto_threshold
                    })
            
            logger.debug(f"Found {len(results)} matches for '{item_name}' (best score: {matches[0][1] if matches else 0})")
            return results
            
        except Exception as e:
            logger.error(f"Error in fuzzy matching for '{item_name}': {e}")
            return []
    
    def suggest_sku(self, item_name: str) -> Optional[Dict[str, Any]]:
        """
        Get best SKU suggestion for item
        
        Args:
            item_name: Name to find SKU for
            
        Returns:
            Best match or None
        """
        matches = self.find_matches(item_name, limit=1)
        return matches[0] if matches else None
    
    def auto_assign_sku(self, item_name: str) -> Optional[str]:
        """
        Automatically assign SKU if confidence is high enough
        
        Args:
            item_name: Name to auto-assign
            
        Returns:
            SKU if auto-assigned, None otherwise
        """
        suggestion = self.suggest_sku(item_name)
        if suggestion and suggestion['is_auto_match']:
            logger.info(f"Auto-assigned SKU {suggestion['sku']} to '{item_name}' (score: {suggestion['score']})")
            return suggestion['sku']
        
        return None
    
    def batch_match_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Batch match multiple items
        
        Args:
            items: List of items to match
            
        Returns:
            Items with SKU suggestions added
        """
        matched_items = []
        
        for item in items:
            item_name = item.get('name', '')
            if not item_name:
                continue
            
            # Get SKU suggestion
            suggestion = self.suggest_sku(item_name)
            
            if suggestion:
                item['sku_suggestion'] = suggestion['sku']
                item['confidence_score'] = suggestion['score']
                item['is_auto_matched'] = suggestion['is_auto_match']
                
                # Auto-assign if threshold met
                if suggestion['is_auto_match']:
                    item['sku'] = suggestion['sku']
                    logger.info(f"Auto-assigned SKU {suggestion['sku']} to '{item_name}'")
            else:
                item['sku_suggestion'] = None
                item['confidence_score'] = 0.0
                item['is_auto_matched'] = False
            
            matched_items.append(item)
        
        logger.info(f"Batch matched {len(matched_items)} items")
        return matched_items
    
    def add_product(self, name: str, sku: str, attributes: Dict[str, Any] = None) -> bool:
        """
        Add new product to database
        
        Args:
            name: Product name
            sku: Product SKU
            attributes: Additional attributes
            
        Returns:
            True if successful
        """
        try:
            db = get_db_session()
            
            # Check if product already exists
            existing = db.query(Product).filter(
                (Product.name == name) | (Product.sku == sku)
            ).first()
            
            if existing:
                logger.warning(f"Product with name '{name}' or SKU '{sku}' already exists")
                db.close()
                return False
            
            # Create new product
            new_product = Product(
                name=name,
                sku=sku,
                attributes_json=str(attributes) if attributes else None
            )
            
            db.add(new_product)
            db.commit()
            db.close()
            
            # Invalidate cache
            self._product_cache = None
            
            logger.info(f"Added new product: {name} ({sku})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add product '{name}': {e}")
            return False
    
    def update_product(self, product_id: int, **kwargs) -> bool:
        """
        Update existing product
        
        Args:
            product_id: Product ID
            **kwargs: Fields to update
            
        Returns:
            True if successful
        """
        try:
            db = get_db_session()
            product = db.query(Product).filter(Product.id == product_id).first()
            
            if not product:
                logger.warning(f"Product with ID {product_id} not found")
                db.close()
                return False
            
            # Update fields
            for field, value in kwargs.items():
                if hasattr(product, field):
                    setattr(product, field, value)
            
            db.commit()
            db.close()
            
            # Invalidate cache
            self._product_cache = None
            
            logger.info(f"Updated product {product_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update product {product_id}: {e}")
            return False
    
    def get_product_stats(self) -> Dict[str, Any]:
        """Get statistics about products in database"""
        try:
            db = get_db_session()
            total_products = db.query(Product).count()
            db.close()
            
            return {
                'total_products': total_products,
                'cache_size': len(self._product_cache) if self._product_cache else 0,
                'auto_threshold': self.auto_threshold,
                'suggest_threshold': self.suggest_threshold
            }
            
        except Exception as e:
            logger.error(f"Failed to get product stats: {e}")
            return {}
