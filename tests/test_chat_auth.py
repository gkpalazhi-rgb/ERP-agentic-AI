import importlib
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient


try:
    import bcrypt  # noqa: F401
    BCRYPT_AVAILABLE = True
except ModuleNotFoundError:
    BCRYPT_AVAILABLE = False


if BCRYPT_AVAILABLE:
    os.environ["DISABLE_INTENT_PRELOAD"] = "1"
    os.environ.setdefault("DATABASE_URL", "sqlite:///./test_chat_auth.db")

    main_module = importlib.import_module("app.main")

    from app.models.conversation import AIConversation
    from app.models.user import User
    from app.services.auth import create_token, hash_password


@unittest.skipUnless(BCRYPT_AVAILABLE, "bcrypt dependency not installed")
class ChatAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main_module.app)

    def setUp(self):
        db = main_module.SessionLocal()
        try:
            db.query(AIConversation).delete()
            db.query(User).delete()
            db.commit()

            user = User(username="student", email="student@test.com", role="employee", password_hash=hash_password("pass123"))
            db.add(user)
            db.commit()
            db.refresh(user)
            self.user_id = user.id
            self.token = create_token(user.id, user.username, user.role)
        finally:
            db.close()

    def test_chat_requires_token(self):
        response = self.client.post("/chat", params={"message": "hello"})
        self.assertEqual(response.status_code, 401)
        body = response.json()
        self.assertEqual(body["error"]["code"], "HTTP_ERROR")

    def test_chat_rejects_invalid_token(self):
        response = self.client.post(
            "/chat",
            params={"message": "hello"},
            headers={"Authorization": "Bearer invalid-token"},
        )
        self.assertEqual(response.status_code, 401)

    def test_chat_uses_authenticated_user_id_not_query_user_id(self):
        with patch.object(main_module, "generate_plan", return_value={"type": "conversation", "response": "ok"}):
            response = self.client.post(
                "/chat",
                params={"message": "hello", "session_id": "s1", "user_id": 9999},
                headers={"Authorization": f"Bearer {self.token}"},
            )
            self.assertEqual(response.status_code, 200)

        db = main_module.SessionLocal()
        try:
            convo = db.query(AIConversation).filter(AIConversation.session_id == "s1").first()
            self.assertIsNotNone(convo)
            self.assertEqual(convo.user_id, self.user_id)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
