from pydantic import BaseModel, EmailStr, ConfigDict
from app.database.models import UserRole
from typing import Optional
from datetime import datetime

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: Optional[UserRole] = UserRole.CUSTOMER

class UserResponse(BaseModel):
    id: int
    email: str
    name: str
    role: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)