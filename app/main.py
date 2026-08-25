from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database.session import engine, Base
from app.routers import users, wallets, transactions, admin

Base.metadata.create_all(bind=engine)
app = FastAPI(title="FinTech Wallet")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router)
app.include_router(wallets.router)
app.include_router(transactions.router)
app.include_router(admin.router)