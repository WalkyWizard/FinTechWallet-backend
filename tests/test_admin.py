import unittest
from decimal import Decimal
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.database.session import get_db
from app.database.models import Base, User, Wallet, Transaction, UserRole
from app.services.auth import create_access_token, hash_password


class TestAdminEndpoints(unittest.TestCase):
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

        admin_user = User(
            email="admin@example.com",
            name="SuperAdmin",
            hashed_password=hash_password("adminpass123"),
            role=UserRole.ADMIN,
            status="active"
        )
        other_admin = User(
            email="admin2@example.com",
            name="OtherAdmin",
            hashed_password=hash_password("adminpass123"),
            role=UserRole.ADMIN,
            status="active"
        )
        customer_user = User(
            email="customer@example.com",
            name="RegularCustomer",
            hashed_password=hash_password("custpass123"),
            role=UserRole.CUSTOMER,
            status="active"
        )
        db.add_all([admin_user, other_admin, customer_user])
        db.commit()
        db.refresh(admin_user)
        db.refresh(other_admin)
        db.refresh(customer_user)

        wallet = Wallet(
            wallet_address="1111222233334444",
            name="Customer Wallet",
            balance=Decimal("100.00"),
            user_id=customer_user.id
        )
        db.add(wallet)
        db.commit()
        db.refresh(wallet)

        tx = Transaction(
            type="deposit",
            amount=Decimal("50.00"),
            status="completed",
            receiver=wallet.wallet_address
        )
        db.add(tx)
        db.commit()

        self.admin_id = admin_user.id
        self.admin_email = admin_user.email
        self.other_admin_id = other_admin.id
        self.customer_id = customer_user.id
        self.customer_email = customer_user.email

        db.close()

        admin_token = create_access_token({"sub": str(self.admin_id), "email": self.admin_email, "role": "admin"})
        self.admin_headers = {"Authorization": f"Bearer {admin_token}"}

        cust_token = create_access_token({"sub": str(self.customer_id), "email": self.customer_email, "role": "customer"})
        self.customer_headers = {"Authorization": f"Bearer {cust_token}"}

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)
        app.dependency_overrides.clear()

    def test_admin_access_forbidden_for_regular_user(self):
        response = self.client.get("/admin/users", headers=self.customer_headers)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_all_users_excludes_admins(self):
        response = self.client.get("/admin/users", headers=self.admin_headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        users = response.json()
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0]["email"], self.customer_email)
        self.assertEqual(users[0]["role"], "customer")

    def test_block_and_unblock_user_success(self):
        block_res = self.client.post(f"/admin/users/{self.customer_id}/block", headers=self.admin_headers)
        self.assertEqual(block_res.status_code, status.HTTP_200_OK)

        db = self.TestingSessionLocal()
        user = db.query(User).filter(User.id == self.customer_id).first()
        self.assertEqual(user.status, "blocked")
        db.close()

        unblock_res = self.client.post(f"/admin/users/{self.customer_id}/unblock", headers=self.admin_headers)
        self.assertEqual(unblock_res.status_code, status.HTTP_200_OK)

        db = self.TestingSessionLocal()
        user = db.query(User).filter(User.id == self.customer_id).first()
        self.assertEqual(user.status, "active")
        db.close()

    def test_cannot_block_admin(self):
        response = self.client.post(f"/admin/users/{self.other_admin_id}/block", headers=self.admin_headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()["detail"], "Cannot block another admin")

    def test_get_all_transactions_with_filters(self):
        response = self.client.get("/admin/transactions?tran_type=all", headers=self.admin_headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()), 1)

        res_dep = self.client.get("/admin/transactions?tran_type=deposit", headers=self.admin_headers)
        self.assertEqual(res_dep.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_dep.json()), 1)

        res_with = self.client.get("/admin/transactions?tran_type=withdraw", headers=self.admin_headers)
        self.assertEqual(res_with.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_with.json()), 0)

        res_user = self.client.get(f"/admin/transactions?user_id={self.customer_id}", headers=self.admin_headers)
        self.assertEqual(res_user.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_user.json()), 1)

    def test_get_user_wallets_success(self):
        response = self.client.get(f"/admin/user/wallets?user_id={self.customer_id}", headers=self.admin_headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        wallets = response.json()
        self.assertEqual(len(wallets), 1)
        self.assertEqual(wallets[0]["wallet_address"], "1111222233334444")
        self.assertEqual(wallets[0]["user_id"], self.customer_id)

    def test_get_user_wallets_forbidden_for_admin_target(self):
        response = self.client.get(f"/admin/user/wallets?user_id={self.other_admin_id}", headers=self.admin_headers)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.json()["detail"], "You can not see admins wallets")

    def test_get_user_wallets_user_not_found(self):
        response = self.client.get("/admin/user/wallets?user_id=9999", headers=self.admin_headers)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.json()["detail"], "User with id 9999 not found")


if __name__ == "__main__":
    unittest.main()