"""
Database initialization and connection management
"""

import logging
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.db.models import Base
from app.utils.config import AppConfig

logger = logging.getLogger(__name__)

# Global engine and session factory
_engine = None
_SessionLocal = None

def init_database(config: AppConfig = None):
    """Initialize database connection and create tables"""
    global _engine, _SessionLocal
    
    if config is None:
        from app.utils.config import load_config
        config = load_config()
    
    # Ensure data directory exists
    db_path = Path(config.database_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Create database URL
    db_url = f"sqlite:///{db_path.absolute()}"
    
    try:
        # Create engine
        _engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False  # Set to True for SQL debugging
        )
        
        # Create session factory
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
        
        # Create tables
        Base.metadata.create_all(bind=_engine)
        
        logger.info(f"Database initialized successfully: {db_path}")
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

def get_db() -> Session:
    """Get database session"""
    if _SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_db_session() -> Session:
    """Get a single database session (for non-generator contexts)"""
    if _SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    
    return _SessionLocal()

def close_database():
    """Close database connection"""
    global _engine
    if _engine:
        _engine.dispose()
        logger.info("Database connection closed")
