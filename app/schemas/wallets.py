from pydantic import BaseModel, ConfigDict, Field
from decimal import Decimal

class WalletCreate(BaseModel):
    wallet_address: str = Field(min_length=16, max_length=16)
    name: str

class WalletResponse(BaseModel):
    id: int
    wallet_address: str
    name: str
    balance: float
    user_id: int

    model_config = ConfigDict(from_attributes=True)