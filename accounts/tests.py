import json

from django.test import TestCase

from .models import User

STRONG_PASSWORD = "kedi-masa-2026"


def post_json(client, url, payload):
    return client.post(url, data=json.dumps(payload), content_type="application/json")


class RegisterTests(TestCase):
    def register(self, **overrides):
        payload = {"username": "ali_k", "email": "ali@example.com", "password": STRONG_PASSWORD}
        payload.update(overrides)
        return post_json(self.client, "/api/auth/register/", payload)

    def test_register_logs_the_user_in_and_hides_email(self):
        response = self.register()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), {"authenticated": True, "username": "ali_k"})
        me = self.client.get("/api/auth/me/")
        self.assertEqual(me.json(), {"authenticated": True, "username": "ali_k"})
        self.assertNotIn("ali@example.com", me.content.decode())

    def test_username_is_unique_case_insensitively(self):
        self.register()
        response = self.register(username="ALI_K", email="other@example.com")
        self.assertEqual(response.status_code, 400)
        self.assertIn("username", response.json()["errors"])

    def test_email_is_unique_case_insensitively(self):
        self.register()
        response = self.register(username="veli", email="ALI@example.com")
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.json()["errors"])

    def test_invalid_fields_return_field_errors(self):
        response = self.register(username="a!", email="not-an-email", password="123")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.json()["errors"]), {"username", "email", "password"})

    def test_username_length_limits(self):
        self.assertEqual(self.register(username="ab").status_code, 400)
        self.assertEqual(self.register(username="a" * 21).status_code, 400)
        self.assertEqual(self.register(username="abc").status_code, 201)

    def test_malformed_body_is_rejected(self):
        response = self.client.post("/api/auth/register/", data="nope", content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get("/api/auth/register/").status_code, 405)


class LoginTests(TestCase):
    def setUp(self):
        User.objects.create_user("ali_k", "ali@example.com", STRONG_PASSWORD)

    def login(self, identifier, password=STRONG_PASSWORD):
        return post_json(self.client, "/api/auth/login/", {"identifier": identifier, "password": password})

    def test_login_with_username_or_email(self):
        for identifier in ("ali_k", "ALI_K", "ali@example.com", "Ali@Example.com"):
            self.client.post("/api/auth/logout/")
            response = self.login(identifier)
            self.assertEqual(response.status_code, 200, identifier)
            self.assertEqual(response.json()["username"], "ali_k")

    def test_wrong_credentials_use_one_generic_message(self):
        wrong_password = self.login("ali_k", "yanlis-parola")
        unknown_user = self.login("kimse")
        self.assertEqual(wrong_password.status_code, 401)
        self.assertEqual(unknown_user.status_code, 401)
        self.assertEqual(wrong_password.json(), unknown_user.json())

    def test_logout(self):
        self.login("ali_k")
        self.assertTrue(self.client.get("/api/auth/me/").json()["authenticated"])
        self.client.post("/api/auth/logout/")
        self.assertFalse(self.client.get("/api/auth/me/").json()["authenticated"])


class PageTests(TestCase):
    def test_pages_render(self):
        for url in ("/giris/", "/kayit/"):
            self.assertEqual(self.client.get(url).status_code, 200)

    def test_logged_in_user_is_redirected_away_and_next_is_validated(self):
        User.objects.create_user("ali_k", "ali@example.com", STRONG_PASSWORD)
        self.client.login(username="ali_k", password=STRONG_PASSWORD)
        self.assertRedirects(self.client.get("/giris/?next=/olustur"), "/olustur", fetch_redirect_response=False)
        self.assertRedirects(self.client.get("/giris/?next=https://evil.example"), "/", fetch_redirect_response=False)
