import unittest
from unittest.mock import patch

from flask import Flask

from app.auth.routes import auth_bp
from app.chat.routes import chat_bp


def _build_app():
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.register_blueprint(auth_bp)
    app.register_blueprint(chat_bp)
    return app


class StaleSessionGuardTests(unittest.TestCase):
    def test_check_auth_clears_stale_session(self):
        app = _build_app()

        with patch("app.auth.session_guard.find_user_by_id", return_value=None):
            with app.test_client() as client:
                with client.session_transaction() as flask_session:
                    flask_session["user_id"] = 1
                    flask_session["username"] = "ghost-user"

                response = client.get("/api/check_auth")

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.get_json(), {"isLoggedIn": False})

                with client.session_transaction() as flask_session:
                    self.assertNotIn("user_id", flask_session)
                    self.assertNotIn("username", flask_session)

    def test_new_chat_rejects_stale_session(self):
        app = _build_app()

        with patch("app.auth.session_guard.find_user_by_id", return_value=None):
            with app.test_client() as client:
                with client.session_transaction() as flask_session:
                    flask_session["user_id"] = 1
                    flask_session["username"] = "ghost-user"

                response = client.post("/api/new_chat")

                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.get_json()["error"], "用户未登录或会话已过期")


if __name__ == "__main__":
    unittest.main()
