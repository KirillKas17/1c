"""
Storage Layer: Database Models and Connection Management.
Supports PostgreSQL for production and SQLite for local testing.
"""
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    uploads = relationship("FileUpload", back_populates="user")
    mappings = relationship("FieldMapping", back_populates="user")

class FileUpload(Base):
    __tablename__ = 'file_uploads'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    file_size_bytes = Column(Integer)
    row_count = Column(Integer)
    industry_profile = Column(String, default='retail')
    
    user = relationship("User", back_populates="uploads")
    dashboard_results = relationship("DashboardResult", back_populates="upload")

class FieldMapping(Base):
    """Stores user-corrected mappings for learning."""
    __tablename__ = 'field_mappings'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    file_signature = Column(String, nullable=False)  # Hash of column names to identify file type
    source_column = Column(String, nullable=False)
    mapped_field = Column(String, nullable=False)
    confidence_score = Column(Float)
    is_user_corrected = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="mappings")

class DashboardResult(Base):
    __tablename__ = 'dashboard_results'
    
    id = Column(Integer, primary_key=True)
    upload_id = Column(Integer, ForeignKey('file_uploads.id'))
    generated_at = Column(DateTime, default=datetime.utcnow)
    metrics_json = Column(JSON)  # Stores calculated KPIs
    forecast_json = Column(JSON)  # Stores forecast data
    components_config = Column(JSON)  # UI layout config
    
    upload = relationship("FileUpload", back_populates="dashboard_results")

class DatabaseManager:
    def __init__(self, db_url: str = None):
        if db_url is None:
            # Default to SQLite for local dev, switch to Postgres via ENV
            db_url = os.getenv("DATABASE_URL", "sqlite:///./dashboard.db")
        
        self.engine = create_engine(
            db_url, 
            echo=False,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20
        )
        self.SessionLocal = sessionmaker(bind=self.engine)

    def init_db(self):
        """Create tables if they don't exist."""
        Base.metadata.create_all(bind=self.engine)

    def get_session(self):
        return self.SessionLocal()

# Initialize default DB manager
db_manager = DatabaseManager()
