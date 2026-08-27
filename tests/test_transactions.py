import unittest
from decimal import Decimal
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.database.session import get_db
from app.database.models import Base, User, Wallet, UserRole
from app.services.auth import create_access_token, hash_password


class TestTransactionsEndpoints(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        self.TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)

        def override_get_db():
            db = self.TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

        db = self.TestingSessionLocal()
        user1 = User(
            email="sender@example.com",
            name="SenderUser",
            hashed_password=hash_password("password123"),
            role=UserRole.CUSTOMER,
            status="active"
        )
        user2 = User(
            email="receiver@example.com",
            name="ReceiverUser",
            hashed_password=hash_password("password123"),
            role=UserRole.CUSTOMER,
            status="active"
        )
        db.add_all([user1, user2])
        db.commit()
        db.refresh(user1)
        db.refresh(user2)

        wallet1 = Wallet(
            wallet_address="1111222233334444",
            name="Sender Wallet",
            balance=Decimal("100.00000000"),
            user_id=user1.id
        )
        wallet2 = Wallet(
            wallet_address="5555666677778888",
            name="Receiver Wallet",
            balance=Decimal("0.00000000"),
            user_id=user2.id
        )
        db.add_all([wallet1, wallet2])
        db.commit()
        db.refresh(wallet1)
        db.refresh(wallet2)

        self.user1_id = user1.id
        self.user1_email = user1.email
        self.user2_id = user2.id
        self.user2_email = user2.email
        self.wallet1_id = wallet1.id
        self.wallet1_address = wallet1.wallet_address
        self.wallet2_id = wallet2.id
        self.wallet2_address = wallet2.wallet_address
        db.close()

        token1 = create_access_token({"sub": str(self.user1_id), "email": self.user1_email, "role": "customer"})
        self.headers_user1 = {"Authorization": f"Bearer {token1}"}

        token2 = create_access_token({"sub": str(self.user2_id), "email": self.user2_email, "role": "customer"})
        self.headers_user2 = {"Authorization": f"Bearer {token2}"}

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)
        app.dependency_overrides.clear()

    def test_deposit_funds_success(self):
        payload = {"wallet_id": self.wallet1_id, "amount": 50.00}
        response = self.client.post("/transactions/deposit", json=payload, headers=self.headers_user1)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(data["type"], "deposit")
        self.assertEqual(data["status"], "completed")
        self.assertEqual(data["receiver"], self.wallet1_address)

        db = self.TestingSessionLocal()
        wallet = db.query(Wallet).filter(Wallet.id == self.wallet1_id).first()
        self.assertEqual(wallet.balance, Decimal("150.00"))
        db.close()

    def test_withdraw_funds_with_fee_success(self):
        payload = {"wallet_id": self.wallet1_id, "amount": 50.00}
        response = self.client.post("/transactions/withdraw", json=payload, headers=self.headers_user1)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(data["type"], "withdraw")
        self.assertEqual(data["status"], "completed")

        db = self.TestingSessionLocal()
        wallet = db.query(Wallet).filter(Wallet.id == self.wallet1_id).first()
        self.assertEqual(wallet.balance, Decimal("49.00"))
        db.close()

    def test_withdraw_insufficient_funds(self):
        payload = {"wallet_id": self.wallet1_id, "amount": 100.00}
        response = self.client.post("/transactions/withdraw", json=payload, headers=self.headers_user1)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_transfer_lifecycle_accept(self):
        transfer_payload = {"sender_wallet_id": self.wallet1_id, "receiver_address": self.wallet2_address, "amount": 50.00}
        res_init = self.client.post("/transactions/transfer", json=transfer_payload, headers=self.headers_user1)
        self.assertEqual(res_init.status_code, status.HTTP_200_OK)
        tx_id = res_init.json()["id"]
        self.assertEqual(res_init.json()["status"], "pending")

        res_pending = self.client.get("/transactions/pending", headers=self.headers_user2)
        self.assertEqual(res_pending.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_pending.json()), 1)
        self.assertEqual(res_pending.json()[0]["id"], tx_id)

        res_accept = self.client.post(f"/transactions/{tx_id}/accept", headers=self.headers_user2)
        self.assertEqual(res_accept.status_code, status.HTTP_200_OK)
        self.assertEqual(res_accept.json()["message"], "Transfer accepted")

        db = self.TestingSessionLocal()
        sender = db.query(Wallet).filter(Wallet.id == self.wallet1_id).first()
        receiver = db.query(Wallet).filter(Wallet.id == self.wallet2_id).first()

        self.assertEqual(sender.balance, Decimal("49.00"))
        self.assertEqual(receiver.balance, Decimal("50.00"))
        db.close()

    def test_transfer_lifecycle_reject(self):
        transfer_payload = {"sender_wallet_id": self.wallet1_id, "receiver_address": self.wallet2_address, "amount": 50.00}
        res_init = self.client.post("/transactions/transfer", json=transfer_payload, headers=self.headers_user1)
        tx_id = res_init.json()["id"]

        res_reject = self.client.post(f"/transactions/{tx_id}/reject", headers=self.headers_user2)
        self.assertEqual(res_reject.status_code, status.HTTP_200_OK)
        self.assertEqual(res_reject.json()["message"], "Transfer rejected. Money returned to sender.")

        db = self.TestingSessionLocal()
        sender = db.query(Wallet).filter(Wallet.id == self.wallet1_id).first()
        receiver = db.query(Wallet).filter(Wallet.id == self.wallet2_id).first()

        self.assertEqual(sender.balance, Decimal("100.00"))
        self.assertEqual(receiver.balance, Decimal("0.00"))
        db.close()

    def test_get_history_with_filters(self):
        self.client.post("/transactions/deposit", json={"wallet_id": self.wallet1_id, "amount": 25.00}, headers=self.headers_user1)
        self.client.post("/transactions/withdraw", json={"wallet_id": self.wallet1_id, "amount": 10.00}, headers=self.headers_user1)

        res_all = self.client.get(f"/transactions/history/{self.wallet1_id}", headers=self.headers_user1)
        self.assertEqual(res_all.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_all.json()), 2)

        res_dep = self.client.get(f"/transactions/history/{self.wallet1_id}?tran_type=deposit", headers=self.headers_user1)
        self.assertEqual(res_dep.status_code, status.HTTP_200_OK)
        data_dep = res_dep.json()
        self.assertEqual(len(data_dep), 1)
        self.assertEqual(data_dep[0]["type"], "deposit")

        res_with = self.client.get(f"/transactions/history/{self.wallet1_id}?tran_type=withdraw", headers=self.headers_user1)
        self.assertEqual(res_with.status_code, status.HTTP_200_OK)
        data_with = res_with.json()
        self.assertEqual(len(data_with), 1)
        self.assertEqual(data_with[0]["type"], "withdraw")

        res_trans = self.client.get(f"/transactions/history/{self.wallet1_id}?tran_type=transfer", headers=self.headers_user1)
        self.assertEqual(res_trans.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_trans.json()), 0)


if __name__ == "__main__":
    unittest.main()