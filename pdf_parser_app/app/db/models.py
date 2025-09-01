"""
Database models for PDF Parser Application
"""

from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.ext.declarative import declared_attr

Base = declarative_base()

class TimestampMixin:
    """Mixin for timestamp fields"""
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Supplier(Base, TimestampMixin):
    """Supplier information"""
    __tablename__ = "suppliers"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, unique=True)
    contact = Column(Text)
    
    # Relationships
    documents = relationship("Document", back_populates="supplier")
    
    def __repr__(self):
        return f"<Supplier(name='{self.name}')>"

class Product(Base, TimestampMixin):
    """Product/SKU information"""
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True)
    sku = Column(String(100), nullable=False, unique=True)
    name = Column(String(500), nullable=False)
    attributes_json = Column(Text)  # JSON string for flexible attributes
    
    # Relationships
    items = relationship("Item", back_populates="product")
    
    def __repr__(self):
        return f"<Product(sku='{self.sku}', name='{self.name}')>"

class Document(Base, TimestampMixin):
    """Document information"""
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    filename = Column(String(500), nullable=False)
    file_path = Column(String(1000), nullable=False)
    date_received = Column(DateTime, default=datetime.utcnow)
    status = Column(String(50), default="pending")  # pending, processing, completed, error
    
    # Relationships
    supplier = relationship("Supplier", back_populates="documents")
    items = relationship("Item", back_populates="document")
    
    def __repr__(self):
        return f"<Document(filename='{self.filename}', status='{self.status}')>"

class Item(Base, TimestampMixin):
    """Parsed item from document"""
    __tablename__ = "items"
    
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    
    # Parsed data
    name = Column(String(500), nullable=False)
    qty = Column(Float, nullable=False)
    unit = Column(String(50))
    price = Column(Float, nullable=False)
    currency = Column(String(10), default="RUB")
    total = Column(Float)
    
    # Matching results
    sku_suggestion = Column(String(100))
    confidence_score = Column(Float)
    is_auto_matched = Column(Boolean, default=False)
    
    # Relationships
    document = relationship("Document", back_populates="items")
    product = relationship("Product", back_populates="items")
    user_actions = relationship("UserAction", back_populates="item")
    
    def __repr__(self):
        return f"<Item(name='{self.name}', qty={self.qty}, price={self.price})>"

class ImportSession(Base, TimestampMixin):
    """Import session information"""
    __tablename__ = "import_sessions"
    
    id = Column(Integer, primary_key=True)
    user = Column(String(100), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    template_used = Column(String(500))
    excel_file_path = Column(String(1000))
    backup_file_path = Column(String(1000))
    
    # Relationships
    user_actions = relationship("UserAction", back_populates="import_session")
    
    def __repr__(self):
        return f"<ImportSession(user='{self.user}', timestamp='{self.timestamp}')>"

class UserAction(Base, TimestampMixin):
    """User actions audit trail"""
    __tablename__ = "user_actions"
    
    id = Column(Integer, primary_key=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=True)
    import_session_id = Column(Integer, ForeignKey("import_sessions.id"), nullable=True)
    action = Column(String(100), nullable=False)  # accept, reject, edit, export
    user = Column(String(100), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    note = Column(Text)
    
    # Relationships
    item = relationship("Item", back_populates="user_actions")
    import_session = relationship("ImportSession", back_populates="user_actions")
    
    def __repr__(self):
        return f"<UserAction(action='{self.action}', user='{self.user}')>"
