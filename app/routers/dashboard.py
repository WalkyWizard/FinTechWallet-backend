from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from decimal import Decimal
from app.database.session import get_db
from app.database.models import User, UserRole, Transaction

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/clients", response_model=dict)
def get_clients(db: Session = Depends(get_db)):
    clients_count = db.query(User).filter(User.role != UserRole.ADMIN).count()
    return {"clients": clients_count}

@router.get("/transactions", response_model=dict)
def get_transactions(db: Session = Depends(get_db)):
    transactions_count = db.query(Transaction).count()
    return {"transactions" : transactions_count}

@router.get("/withdraw", response_model=dict)
def get_withdraw(db: Session = Depends(get_db)):
    total_amount = db.query(func.sum(Transaction.amount)).filter(Transaction.type != "deposit", Transaction.status == "completed").scalar()
    if total_amount is None:
        total_amount = Decimal("0.00")
    return {"total" : total_amount}