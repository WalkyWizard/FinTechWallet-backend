from pydantic import BaseModel, ConfigDict, Field, field_serializer
from decimal import Decimal
from datetime import datetime
from typing import Optional

class TransactionRequest(BaseModel):
    wallet_id: int
    amount: Decimal = Field(gt=0)

class TransactionResponse(BaseModel):
    id: int
    type: str
    amount: Decimal
    status: str
    sender: Optional[str] = None
    receiver: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("amount")
    def serialize_amount(self, amount: Decimal, _info) -> str:
        return f"{amount:.8f}"

class TransferRequest(BaseModel):
    sender_wallet_id: int
    receiver_address: str
    amount: Decimal = Field(gt=0)