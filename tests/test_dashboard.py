import unittest
from decimal import Decimal
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.database.session import get_db
from app.database.models import Base, User, Transaction, UserRole
from app.services.auth import hash_password


class TestDashboardEndpoints(unittest.TestCase):
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

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)
        app.dependency_overrides.clear()

    def test_get_clients_count(self):
        db = self.TestingSessionLocal()
        u1 = User(email="cust1@test.com", name="Cust1", hashed_password=hash_password("pass"), role=UserRole.CUSTOMER)
        u2 = User(email="cust2@test.com", name="Cust2", hashed_password=hash_password("pass"), role=UserRole.CUSTOMER)
        admin = User(email="admin@test.com", name="Admin", hashed_password=hash_password("pass"), role=UserRole.ADMIN)
        db.add_all([u1, u2, admin])
        db.commit()
        db.close()

        response = self.client.get("/dashboard/clients")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("clients", data)
        self.assertEqual(data["clients"], 2)

    def test_get_transactions_count(self):
        db = self.TestingSessionLocal()
        tx1 = Transaction(type="deposit", amount=Decimal("10.00"), status="completed")
        tx2 = Transaction(type="withdraw", amount=Decimal("20.00"), status="completed")
        tx3 = Transaction(type="transfer", amount=Decimal("30.00"), status="pending")
        db.add_all([tx1, tx2, tx3])
        db.commit()
        db.close()

        response = self.client.get("/dashboard/transactions")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("transactions", data)
        self.assertEqual(data["transactions"], 3)

    def test_get_withdraw_sum(self):
        db = self.TestingSessionLocal()
        tx_withdraw = Transaction(type="withdraw", amount=Decimal("50.00"), status="completed")
        tx_transfer = Transaction(type="transfer", amount=Decimal("25.50"), status="completed")
        tx_deposit = Transaction(type="deposit", amount=Decimal("100.00"), status="completed")
        tx_pending_withdraw = Transaction(type="withdraw", amount=Decimal("40.00"), status="pending")
        db.add_all([tx_withdraw, tx_transfer, tx_deposit, tx_pending_withdraw])
        db.commit()
        db.close()

        response = self.client.get("/dashboard/withdraw")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(Decimal(str(data["total"])), Decimal("75.50"))

    def test_get_withdraw_sum_empty(self):
        response = self.client.get("/dashboard/withdraw")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(Decimal(str(data["total"])), Decimal("0.00"))

    def test_get_user_time(self):
        db = self.TestingSessionLocal()
        u1 = User(email="cust1@test.com", name="Cust1", hashed_password=hash_password("pass"), role=UserRole.CUSTOMER)
        u2 = User(email="cust2@test.com", name="Cust2", hashed_password=hash_password("pass"), role=UserRole.CUSTOMER)
        admin = User(email="admin@test.com", name="Admin", hashed_password=hash_password("pass"), role=UserRole.ADMIN)
        db.add_all([u1, u2, admin])
        db.commit()
        db.close()

        response = self.client.get("/dashboard/users/time")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("created_at_list", data)
        self.assertEqual(len(data["created_at_list"]), 2)


if __name__ == "__main__":
    unittest.main()