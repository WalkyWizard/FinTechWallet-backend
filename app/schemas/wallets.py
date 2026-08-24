from pydantic import BaseModel, ConfigDict
from decimal import Decimal

class WalletCreate(BaseModel):
    wallet_address: str
    name: str

class WalletResponse(BaseModel):
    id: int
    wallet_address: str
    name: str
    balance: float
    user_id: int

    model_config = ConfigDict(from_attributes=True)