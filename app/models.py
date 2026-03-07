import os
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, Integer, BigInteger, Index, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class CompanyProfile(Base):
    """
    Relational table storing fallback company information.
    """
    __tablename__ = "company_profiles"
    
    ticker = Column(String(10), primary_key=True, index=True)
    name = Column(String(255))
    sector = Column(String(100))
    industry = Column(String(100))
    summary = Column(String)
    employees = Column(Integer)
    city = Column(String(100))
    country = Column(String(100))
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

class AIFundamentals(Base):
    """
    Relational table storing AI-generated fundamental analysis.
    """
    __tablename__ = "ai_fundamentals"
    
    ticker = Column(String(10), primary_key=True, index=True)
    story = Column(String)
    porter = Column(String)
    competitors = Column(String)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

class UserQueryLog(Base):
    """
    Relational log tracking ticker searches to dynamically calculate Top 10 lists.
    """
    __tablename__ = "query_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), index=True, nullable=False)
    query_type = Column(String(50)) # e.g., 'chart', 'fundamentals', 'agent_tool'
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)

class StockDailyPrice(Base):
    """
    TimescaleDB Hypertable for storing daily OHLC+V data.
    """
    __tablename__ = "stock_daily_prices"
    
    # TimescaleDB requires the time column to be part of the primary key
    time = Column(DateTime(timezone=True), primary_key=True, index=True)
    ticker = Column(String(10), primary_key=True, index=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(BigInteger)
    
    # Compound index for fast specific-stock queries
    __table_args__ = (
        Index('idx_ticker_time_daily', ticker, time.desc()),
    )

class StockWeeklyPrice(Base):
    """
    TimescaleDB Hypertable for storing aggregated weekly OHLC+V data.
    """
    __tablename__ = "stock_weekly_prices"
    
    time = Column(DateTime(timezone=True), primary_key=True, index=True)
    ticker = Column(String(10), primary_key=True, index=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(BigInteger)
    
    __table_args__ = (
        Index('idx_ticker_time_weekly', ticker, time.desc()),
    )
