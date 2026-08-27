from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from enum import Enum
from sqlalchemy import desc, or_
from app.database.session import get_db
from app.database.models import User
from app.schemas.users import UserResponse
from app.dependencies import get_current_admin_user
from app.database.models import Transaction
from app.schemas.transactions import TransactionResponse
from app.schemas.wallets import WalletResponse

router = APIRouter(prefix="/admin", tags=["Admin"], dependencies=[Depends(get_current_admin_user)])

class TransactionTypeFilter(str, Enum):
    all = "all"
    deposit = "deposit"
    withdraw = "withdraw"
    transfer = "transfer"

@router.get("/users", response_model=List[UserResponse])
def get_all_users(db: Session = Depends(get_db)):
    users = db.query(User).filter(User.role != "admin").all()
    return users

@router.post("/users/{user_id}/block")
def block_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role == "admin":
        raise HTTPException(status_code=400, detail="Cannot block another admin")
    if user.status == "blocked":
        return {"message": "User is already blocked"}

    user.status = "blocked"
    db.commit()
    return {"message": f"User {user.email} has been successfully blocked"}

@router.post("/users/{user_id}/unblock")
def unblock_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role == "admin":
        raise HTTPException(status_code=400, detail="Cannot unblock an admin")
    if user.status == "active":
        return {"message": "User is already active"}

    user.status = "active"
    db.commit()
    return {"message": f"User {user.email} has been successfully unblocked"}

@router.get("/transactions", response_model=List[TransactionResponse])
def get_all_transactions(tran_type: TransactionTypeFilter = Query(TransactionTypeFilter.all), user_id: Optional[int] = Query(None), db: Session = Depends(get_db)):
    query = db.query(Transaction)

    if tran_type != TransactionTypeFilter.all:
        query = query.filter(Transaction.type == tran_type.value)

    if user_id is not None:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with id {user_id} not found"
            )

        wallet_addresses = [wallet.wallet_address for wallet in user.wallets]
        if not wallet_addresses:
            return []

        query = query.filter(
            or_(
                Transaction.sender.in_(wallet_addresses),
                Transaction.receiver.in_(wallet_addresses)
            )
        )
    transactions = query.order_by(desc(Transaction.created_at)).all()
    return transactions

@router.get("/user/wallets", response_model=List[WalletResponse])
def get_user_wallets(user_id: Optional[int] = Query(None), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {user_id} not found"
        )
    if user.role == "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You can not see admins wallets"
        )
    return user.wallets