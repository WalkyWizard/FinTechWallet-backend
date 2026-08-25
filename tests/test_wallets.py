import unittest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.database.session import get_db
from app.database.models import Base
from app.services.auth import create_access_token, hash_password
from app.database.models import User, UserRole


class TestWalletsEndpoints(unittest.TestCase):
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
        self.user1 = User(
            email="user1@example.com",
            name="UserOne",
            hashed_password=hash_password("password123"),
            role=UserRole.CUSTOMER
        )

        self.user2 = User(
            email="user2@example.com",
            name="UserTwo",
            hashed_password=hash_password("password123"),
            role=UserRole.CUSTOMER
        )
        db.add_all([self.user1, self.user2])
        db.commit()
        db.refresh(self.user1)
        db.refresh(self.user2)
        db.close()

        token1 = create_access_token({"sub": str(self.user1.id), "email": self.user1.email, "role": self.user1.role.value if hasattr(self.user1.role, "value") else str(self.user1.role)})
        self.headers_user1 = {"Authorization": f"Bearer {token1}"}

        token2 = create_access_token({"sub": str(self.user2.id), "email": self.user2.email, "role": self.user2.role.value if hasattr(self.user2.role, "value") else str(self.user2.role)})
        self.headers_user2 = {"Authorization": f"Bearer {token2}"}

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)
        app.dependency_overrides.clear()

    def test_create_wallet_success(self):
        payload = {"wallet_address": "1234567890123456", "name": "Main"}
        response = self.client.post("/wallets/", json=payload, headers=self.headers_user1)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(data["wallet_address"], payload["wallet_address"])
        self.assertEqual(data["name"], payload["name"])
        self.assertEqual(data["balance"], 0.0)
        self.assertEqual(data["user_id"], self.user1.id)

    def test_create_wallet_invalid_address_length(self):
        payload_short = {"wallet_address": "short_address", "name": "Invalid"}
        response = self.client.post("/wallets/", json=payload_short, headers=self.headers_user1)
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

        payload_long = {"wallet_address": "12345678901234567890", "name": "Invalid"}
        response = self.client.post("/wallets/", json=payload_long, headers=self.headers_user1)
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

    def test_create_duplicate_wallet_address(self):
        payload = {"wallet_address": "1234567890123456", "name": "First Wallet"}
        self.client.post("/wallets/", json=payload, headers=self.headers_user1)
        response = self.client.post("/wallets/", json=payload, headers=self.headers_user1)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()["detail"], "Wallet with this address already exists")

    def test_get_user_wallets(self):
        self.client.post("/wallets/", json={"wallet_address": "1111111111111111", "name": "W1"}, headers=self.headers_user1)
        self.client.post("/wallets/", json={"wallet_address": "2222222222222222", "name": "W2"}, headers=self.headers_user1)

        response = self.client.get("/wallets/user", headers=self.headers_user1)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["wallet_address"], "1111111111111111")
        self.assertEqual(data[1]["wallet_address"], "2222222222222222")

    def test_get_single_wallet_success(self):
        create_res = self.client.post("/wallets/", json={"wallet_address": "1234567890123456", "name": "Savings"}, headers=self.headers_user1)
        wallet_id = create_res.json()["id"]

        response = self.client.get(f"/wallets/user/{wallet_id}", headers=self.headers_user1)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["id"], wallet_id)
        self.assertEqual(data["name"], "Savings")

    def test_get_other_users_wallet_not_found(self):
        create_res = self.client.post("/wallets/", json={"wallet_address": "1234567890123456", "name": "User1 Wallet"}, headers=self.headers_user1)
        wallet_id = create_res.json()["id"]
        response = self.client.get(f"/wallets/user/{wallet_id}", headers=self.headers_user2)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.json()["detail"], "Wallet not found")

    def test_unauthorized_access(self):
        response = self.client.post("/wallets/", json={"wallet_address": "1234567890123456", "name": "No Auth"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


if __name__ == "__main__":
    unittest.main()