from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc
from typing import List
from decimal import Decimal
from app.database.session import get_db
from app.database.models import User, Wallet, Transaction
from app.schemas.transactions import TransactionRequest, TransactionResponse, TransferRequest
from app.dependencies import get_current_user, get_current_user_allow_blocked

router = APIRouter(prefix="/transactions", tags=["Transactions"])
FEE_PERCENT = Decimal("0.02")

@router.post("/deposit", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def deposit_funds(data: TransactionRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    wallet = db.query(Wallet).filter(Wallet.id == data.wallet_id, Wallet.user_id == current_user.id).first()

    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found or does not belong to you"
        )

    wallet.balance += data.amount
    transaction = Transaction(
        type="deposit",
        amount=data.amount,
        status="completed",
        receiver=wallet.wallet_address
    )

    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction

@router.post("/withdraw", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def withdraw_funds(data: TransactionRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    wallet = db.query(Wallet).filter(Wallet.id == data.wallet_id, Wallet.user_id == current_user.id).first()

    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found or does not belong to you"
        )

    fee = data.amount * FEE_PERCENT
    total = data.amount + fee

    if wallet.balance < total:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient balance. Total needed with 2% fee: {total}"
        )

    wallet.balance -= total
    transaction = Transaction(
        type="withdraw",
        amount=data.amount,
        status="completed",
        sender=wallet.wallet_address,
    )

    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction

@router.post("/transfer", response_model=TransactionResponse)
def initiate_transfer(data: TransferRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    sender_wallet = db.query(Wallet).filter(Wallet.id == data.sender_wallet_id, Wallet.user_id == current_user.id).first()

    if not sender_wallet:
        raise HTTPException(status_code=404, detail="Sender wallet not found")
    if sender_wallet.wallet_address == data.receiver_address:
        raise HTTPException(status_code=400, detail="Cannot transfer to the same wallet")

    fee = data.amount * FEE_PERCENT
    total = data.amount + fee

    if sender_wallet.balance < total:
        raise HTTPException(status_code=400, detail=f"Not enough money. Total needed with 2% fee: {total}")

    receiver_wallet = db.query(Wallet).filter(Wallet.wallet_address == data.receiver_address).first()
    if not receiver_wallet:
        raise HTTPException(status_code=404, detail="Receiver wallet not found")

    sender_wallet.balance -= total
    transaction = Transaction(
        type="transfer",
        amount=data.amount,
        status="pending",
        sender=sender_wallet.wallet_address,
        receiver=data.receiver_address
    )

    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction

@router.get("/pending", response_model=List[TransactionResponse])
def get_pending_transfers(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user_addresses = [wallet.wallet_address for wallet in current_user.wallets]
    pending = db.query(Transaction).filter(Transaction.receiver.in_(user_addresses), Transaction.status == "pending", Transaction.type == "transfer").all()
    return pending

@router.post("/{transaction_id}/accept")
def accept_transfer(transaction_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    tx = db.query(Transaction).filter(Transaction.id == transaction_id, Transaction.status == "pending", Transaction.type == "transfer").first()
    if not tx:
        raise HTTPException(status_code=404, detail="Pending transaction not found")

    receiver_wallet = db.query(Wallet).filter(Wallet.wallet_address == tx.receiver, Wallet.user_id == current_user.id).first()
    if not receiver_wallet:
        raise HTTPException(status_code=403, detail="You do not own the receiving wallet")

    receiver_wallet.balance += tx.amount
    tx.status = "completed"
    db.commit()
    return {"message": "Transfer accepted", "transaction_id": tx.id}

@router.post("/{transaction_id}/reject")
def reject_transfer(transaction_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    tx = db.query(Transaction).filter(Transaction.id == transaction_id, Transaction.status == "pending", Transaction.type == "transfer").first()
    if not tx:
        raise HTTPException(status_code=404, detail="Pending transaction not found")

    receiver_wallet = db.query(Wallet).filter(Wallet.wallet_address == tx.receiver, Wallet.user_id == current_user.id).first()
    if not receiver_wallet:
        raise HTTPException(status_code=403, detail="You do not own the receiving wallet")

    sender_wallet = db.query(Wallet).filter(Wallet.wallet_address == tx.sender).first()
    if sender_wallet:
        refund_amount = tx.amount + (tx.amount * FEE_PERCENT)
        sender_wallet.balance += refund_amount

    tx.status = "failed"
    db.commit()
    return {"message": "Transfer rejected. Money returned to sender.", "transaction_id": tx.id}

@router.get("/history/{wallet_id}", response_model=List[TransactionResponse])
def get_transaction_history(wallet_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_allow_blocked)):
    wallet = db.query(Wallet).filter(Wallet.id == wallet_id, Wallet.user_id == current_user.id).first()
    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found or does not belong to you"
        )

    transactions = db.query(Transaction).filter(or_(Transaction.sender == wallet.wallet_address, Transaction.receiver == wallet.wallet_address)).order_by(desc(Transaction.created_at))
    return transactions