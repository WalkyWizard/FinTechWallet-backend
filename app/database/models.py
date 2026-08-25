import enum
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, CheckConstraint, func
from sqlalchemy.orm import relationship
from app.database.session import Base
from datetime import datetime

class UserRole(str, enum.Enum):
    CUSTOMER = "customer"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    name = Column(String, unique=True, index=True, nullable=False)
    role = Column(String, default=UserRole.CUSTOMER, nullable=False)
    status = Column(String, default="active", nullable=False)  # active or blocked
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    wallets = relationship("Wallet", back_populates="owner", cascade="all, delete-orphan")


class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True, index=True)
    wallet_address = Column(String, unique=True, index=True, nullable=False)
    name = Column(String,nullable=False)
    balance = Column(Numeric(precision=18, scale=8), nullable=False, default=0)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    owner = relationship("User", back_populates="wallets")

    __table_args__ = (
        CheckConstraint(func.length(wallet_address) == 16, name="check_wallet_address_length_16"),
    )

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(String, index=True, nullable=False) # deposit, withdraw or transfer
    amount = Column(Numeric(precision=18, scale=8), nullable=False)
    status = Column(String, index=True, nullable=False) # pending, completed or failed
    sender = Column(String, index=True, nullable=True)
    receiver = Column(String, index=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)