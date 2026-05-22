import os
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, Integer, BigInteger, Index, ForeignKey, func, UniqueConstraint
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


class Portfolio(Base):
    """
    A user portfolio. Supports multiple portfolios per user in the future.
    """
    __tablename__ = "portfolios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    name = Column(String(255), nullable=False, default="My Portfolio")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PortfolioHolding(Base):
    """
    An individual stock position inside a portfolio.
    """
    __tablename__ = "portfolio_holdings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False, index=True)
    ticker = Column(String(10), nullable=False)
    shares = Column(Float, nullable=False)
    avg_cost_basis = Column(Float, nullable=False)
    added_at = Column(DateTime(timezone=True), server_default=func.now())


class Transaction(Base):
    """
    Individual transaction record imported from Trading 212.
    Every buy/sell/dividend is stored as a separate row.
    Holdings are computed from the transaction log.
    """
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False, index=True)
    external_id = Column(String(50), nullable=True)  # T212 transaction ID for dedup
    action = Column(String(50), nullable=False)       # "Market buy", "Market sell", "Dividend (Dividend)", etc.
    ticker = Column(String(10), nullable=False, index=True)
    name = Column(String(255))
    isin = Column(String(20))
    shares = Column(Float, nullable=False)
    price_per_share = Column(Float, nullable=False)
    currency = Column(String(10))                     # Currency of price (e.g., "USD")
    exchange_rate = Column(Float)                     # FX rate at time of transaction
    total_in_local = Column(Float)                    # Total in account currency (GBP)
    result_in_local = Column(Float)                   # Realized result from T212 (for sells)
    executed_at = Column(DateTime(timezone=True), nullable=False, index=True)
    imported_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("portfolio_id", "external_id", name="uq_portfolio_external_id"),
        Index("idx_txn_portfolio_ticker", "portfolio_id", "ticker"),
    )


class User(Base):
    """
    User account for authentication and linking.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    name = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class LinkedAccount(Base):
    """
    Relationship between two users for unified viewing and joint expenses.
    """
    __tablename__ = "linked_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    linked_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Expense(Base):
    """
    Individual expense transaction.
    """
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(DateTime(timezone=True), nullable=False, index=True)
    category = Column(String(100), nullable=False)
    amount = Column(Float, nullable=False)
    description = Column(String(255))
    is_joint = Column(Integer, default=0) # 0 for false, 1 for true (SQLite compat boolean)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Income(Base):
    """
    Individual income transaction.
    """
    __tablename__ = "income"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(DateTime(timezone=True), nullable=False, index=True)
    source = Column(String(100), nullable=False)
    amount = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ManualAsset(Base):
    """
    Manual assets like Real Estate, Cash, Vehicles.
    """
    __tablename__ = "manual_assets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_type = Column(String(100), nullable=False) # e.g. "Real Estate", "Cash"
    value = Column(Float, nullable=False)
    description = Column(String(255))
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class NetWorthSnapshot(Base):
    """
    Daily/Monthly snapshot of total net worth.
    """
    __tablename__ = "net_worth_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(DateTime(timezone=True), nullable=False, index=True)
    total_assets = Column(Float, nullable=False) # Computed Portfolio + ManualAssets
    total_liabilities = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
