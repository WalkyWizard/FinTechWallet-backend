import unittest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.database.session import get_db
from app.database.models import Base, UserRole


class TestAuthEndpoints(unittest.TestCase):
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

    def test_register_user_success(self):
        payload = {"email": "alex@example.com", "name": "Alex", "password": "password123"}
        response = self.client.post("/auth/register", json=payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(data["message"], "User successfully registered")
        self.assertIn("user_id", data)

    def test_register_duplicate_user(self):
        payload = {
            "email": "duplicate@example.com",
            "name": "DuplicateUser",
            "password": "password123"
        }
        self.client.post("/auth/register", json=payload)
        response = self.client.post("/auth/register", json=payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()["detail"], "User with this email or name already exists")

    def test_login_success(self):
        self.client.post("/auth/register", json={"email": "login@example.com", "name": "LoginUser", "password": "mypassword"})
        response = self.client.post("/auth/login", json={"email": "login@example.com", "password": "mypassword"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("access_token", data)
        self.assertEqual(data["token_type"], "bearer")

    def test_login_invalid_password(self):
        self.client.post("/auth/register", json={"email": "user2@example.com", "name": "UserTwo", "password": "correctpassword"})
        response = self.client.post("/auth/login", json={"email": "user2@example.com", "password": "wrongpassword"})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.json()["detail"], "Invalid email or password")

    def test_swagger_login(self):
        self.client.post("/auth/register", json={"email": "admin@example.com", "name": "AdminUser", "password": "adminpassword"})
        response = self.client.post("/auth/swagger-login", data={"username": "admin@example.com", "password": "adminpassword"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("access_token", data)


if __name__ == "__main__":
    unittest.main()