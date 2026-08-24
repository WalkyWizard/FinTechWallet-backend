from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database.session import get_db
from app.database.models import User, Wallet
from app.schemas.wallets import WalletCreate, WalletResponse
from app.dependencies import get_current_user

router = APIRouter(prefix="/wallets", tags=["Wallets"])

@router.post("/", response_model=WalletResponse, status_code=status.HTTP_201_CREATED)
def create_wallet(wallet_data: WalletCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    existing_wallet = db.query(Wallet).filter(Wallet.wallet_address == wallet_data.wallet_address).first()
    if existing_wallet:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Wallet with this address already exists"
        )

    new_wallet = Wallet(
        wallet_address=wallet_data.wallet_address,
        name=wallet_data.name,
        user_id=current_user.id
    )

    db.add(new_wallet)
    db.commit()
    db.refresh(new_wallet)

    return new_wallet

@router.get("/user", response_model=List[WalletResponse])
def get_user_wallets(current_user: User = Depends(get_current_user)):
    return current_user.wallets

@router.get("/user/{wallet_id}", response_model=WalletResponse)
def get_single_wallet(wallet_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    wallet = db.query(Wallet).filter(Wallet.id == wallet_id, Wallet.user_id == current_user.id).first()

    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found"
        )
    return wallet