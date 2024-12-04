from datetime import datetime
from typing import Optional

from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, DateTime, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from constants import SQL_DATABASE_URI

Base = declarative_base()


class TimeMixin:
    """
    Mixin for adding created_at and updated_at timestamps
    """

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class UserMixin:
    """
    Mixin for adding created_by and updated_by user tracking
    """

    created_by = Column(String(255), ForeignKey("users.sub"), nullable=False)
    updated_by = Column(String(255), ForeignKey("users.sub"), nullable=False)


class User(Base, TimeMixin):
    __tablename__ = "users"

    sub = Column(String(255), primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(255))
    last_login_at = Column(DateTime(timezone=True))

    # Relationships
    text_entries = relationship("TextEntry", back_populates="user")
    tts_requests = relationship("TTSRequest", back_populates="user", foreign_keys="TTSRequest.user_sub")
    usage_statistics = relationship("UsageStatistic", back_populates="user")


class TextEntry(Base, TimeMixin):
    __tablename__ = "text_entries"

    text_id = Column(String(50), primary_key=True)
    user_sub = Column(String(255), ForeignKey("users.sub"), nullable=False)
    full_text = Column(Text, nullable=False)
    url = Column(String(2048))

    # Relationships
    user = relationship("User", back_populates="text_entries")
    tts_requests = relationship("TTSRequest", back_populates="text_entry")

    # Indexes
    __table_args__ = (Index("idx_text_entries_user_sub", "user_sub"),)


class TTSRequest(Base, TimeMixin, UserMixin):
    __tablename__ = "tts_requests"

    id = Column(Integer, primary_key=True)
    text_entry_id = Column(String(50), ForeignKey("text_entries.text_id"), nullable=False)
    user_sub = Column(String(255), ForeignKey("users.sub"), nullable=False)
    sentence_text = Column(Text, nullable=False)
    sentence_index = Column(Integer, nullable=False)
    audio_id = Column(String(50), nullable=False)
    character_count = Column(Integer, nullable=False)
    processing_time_ms = Column(Integer)
    voice_model = Column(String(50), default="aura-asteria-en")
    status = Column(String(20), default="completed")
    error_message = Column(Text)

    # Relationships
    user = relationship("User", back_populates="tts_requests", foreign_keys="TTSRequest.user_sub")
    created_by_user = relationship("User", foreign_keys="TTSRequest.created_by")
    updated_by_user = relationship("User", foreign_keys="TTSRequest.updated_by")
    text_entry = relationship("TextEntry", back_populates="tts_requests")

    # Indexes
    __table_args__ = (
        Index("idx_tts_requests_user_sub", "user_sub"),
        Index("idx_tts_requests_created_at", "created_at"),
        Index("idx_tts_requests_audio_id", "audio_id"),
    )


class UsageStatistic(Base, TimeMixin):
    __tablename__ = "usage_statistics"

    id = Column(Integer, primary_key=True)
    user_sub = Column(String(255), ForeignKey("users.sub"), nullable=False)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    total_requests = Column(Integer, default=0)
    total_characters = Column(Integer, default=0)
    total_processing_time_ms = Column(Integer, default=0)

    # Relationships
    user = relationship("User", back_populates="usage_statistics")

    # Indexes
    __table_args__ = (Index("idx_usage_statistics_user_time", "user_sub", "year", "month"),)


def build_engine():
    engine = create_engine(SQL_DATABASE_URI)

    def init_db():
        """Initialize the database by creating all tables"""
        Base.metadata.create_all(engine)

    def drop_db():
        """Drop all tables - use with caution!"""
        Base.metadata.drop_all(engine)

    return engine, init_db, drop_db
