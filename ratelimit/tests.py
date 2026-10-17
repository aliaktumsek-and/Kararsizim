import json
from datetime import timedelta
from unittest import mock

from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from accounts.models import User
from polls.models import Option, Poll, Vote
from polls.tests import make_poll

from . import utils
from .models import RateLimitHit
from .utils import Rule

PASSWORD = "kedi-masa-2026"
TINY = Rule("test-scope", 3, 60)


def post(client, url, payload, **extra):
    return client.post(url, data=json.dumps(payload), content_type="application/json", **extra)


class SlidingWindowTests(TestCase):
    def test_allows_up_to_the_limit_then_blocks(self):
        for _ in range(3):
            self.assertEqual(utils.hit(TINY, "k"), 0)
        wait = utils.hit(TINY, "k")
        self.assertGreater(wait, 0)
        self.assertLessEqual(wait, 60)

    def test_blocked_attempts_are_not_recorded(self):
        for _ in range(3):
            utils.hit(TINY, "k")
        for _ in range(5):
            utils.hit(TINY, "k")
        self.assertEqual(RateLimitHit.objects.count(), 3)

    def test_keys_and_scopes_are_independent(self):
        for _ in range(3):
            utils.hit(TINY, "a")
        self.assertEqual(utils.hit(TINY, "b"), 0)
        self.assertEqual(utils.hit(Rule("other", 3, 60), "a"), 0)

    def test_window_slides(self):
        for _ in range(3):
            utils.hit(TINY, "k")
        RateLimitHit.objects.update(created_at=timezone.now() - timedelta(seconds=61))
        self.assertEqual(utils.hit(TINY, "k"), 0)

    def test_every_rule_must_pass(self):
        strict = Rule("strict", 1, 60)
        loose = Rule("loose", 5, 60)
        self.assertEqual(utils.hit((loose, strict), "k"), 0)
        self.assertGreater(utils.hit((loose, strict), "k"), 0)
        self.assertEqual(RateLimitHit.objects.filter(scope="loose").count(), 1)

    def test_only_a_keyed_hash_is_stored(self):
        utils.hit(TINY, "203.0.113.7")
        row = RateLimitHit.objects.get()
        self.assertEqual(len(row.key_hash), 64)
        self.assertNotIn("203.0.113.7", row.key_hash)
        self.assertNotIn("203.0.113.7", f"{row.scope}{row.created_at}")

    def test_old_rows_are_pruned(self):
        RateLimitHit.objects.create(scope="x", key_hash="0" * 64, created_at=timezone.now() - timedelta(days=2))
        with mock.patch.object(utils.random, "random", return_value=0.0):
            utils.record(TINY, "k")
        self.assertFalse(RateLimitHit.objects.filter(scope="x").exists())
        self.assertEqual(RateLimitHit.objects.filter(scope=TINY.scope).count(), 1)

    def test_too_many_response(self):
        response = utils.too_many(125)
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response["Retry-After"], "125")
        self.assertIn("3 dakika", json.loads(response.content)["errors"]["__all__"][0])


class ClientIpTests(TestCase):
    def request(self, **meta):
        return RequestFactory().get("/", **meta)

    @override_settings(TRUST_PROXY_HEADERS=True)
    def test_uses_first_forwarded_address_behind_a_proxy(self):
        request = self.request(HTTP_X_FORWARDED_FOR="198.51.100.4, 10.0.0.1", REMOTE_ADDR="10.0.0.1")
        self.assertEqual(utils.client_ip(request), "198.51.100.4")

    @override_settings(TRUST_PROXY_HEADERS=False)
    def test_ignores_forwarded_header_when_not_trusted(self):
        request = self.request(HTTP_X_FORWARDED_FOR="198.51.100.4", REMOTE_ADDR="127.0.0.1")
        self.assertEqual(utils.client_ip(request), "127.0.0.1")


class LoginRateLimitTests(TestCase):
    URL = "/api/auth/login/"

    def setUp(self):
        User.objects.create_user("ali_k", "ali@example.com", PASSWORD)

    def login(self, identifier="ali_k", password=PASSWORD, **extra):
        return post(self.client, self.URL, {"identifier": identifier, "password": password}, **extra)

    def test_account_is_locked_after_five_failures_even_with_the_right_password(self):
        for _ in range(5):
            self.assertEqual(self.login(password="yanlis-parola").status_code, 401)
        blocked = self.login()
        self.assertEqual(blocked.status_code, 429)
        self.assertIn("Retry-After", blocked)
        self.assertFalse(self.client.get("/api/auth/me/").json()["authenticated"])

    def test_lockout_is_per_account_and_case_insensitive(self):
        for _ in range(5):
            self.login(identifier="ALI_K", password="yanlis-parola")
        self.assertEqual(self.login(identifier="ali_k").status_code, 429)
        User.objects.create_user("veli", "veli@example.com", PASSWORD)
        self.assertEqual(self.login(identifier="veli").status_code, 200)

    def test_unknown_accounts_are_limited_the_same_way(self):
        for _ in range(5):
            self.assertEqual(self.login(identifier="yok", password="x").status_code, 401)
        self.assertEqual(self.login(identifier="yok", password="x").status_code, 429)

    def test_success_resets_the_failure_counter(self):
        for _ in range(4):
            self.login(password="yanlis-parola")
        self.assertEqual(self.login().status_code, 200)
        self.client.post("/api/auth/logout/")
        for _ in range(4):
            self.assertEqual(self.login(password="yanlis-parola").status_code, 401)

    def test_ip_limit_stops_password_spraying(self):
        with mock.patch("accounts.views.LOGIN_IP", Rule("login-ip", 3, 900)):
            for i in range(3):
                self.assertEqual(self.login(identifier=f"kimse{i}", password="x").status_code, 401)
            self.assertEqual(self.login(identifier="baska", password="x").status_code, 429)
            self.assertEqual(self.login().status_code, 429)  # even the real account, same IP

    def test_other_ips_are_not_affected(self):
        with mock.patch("accounts.views.LOGIN_IP", Rule("login-ip", 2, 900)):
            for _ in range(2):
                self.login(identifier="x1", password="x", REMOTE_ADDR="198.51.100.1")
            self.assertEqual(self.login(identifier="x2", password="x", REMOTE_ADDR="198.51.100.1").status_code, 429)
            self.assertEqual(self.login(REMOTE_ADDR="198.51.100.2").status_code, 200)


class RegisterRateLimitTests(TestCase):
    def register(self, n, **extra):
        return post(
            self.client,
            "/api/auth/register/",
            {"username": f"kisi_{n}", "email": f"kisi{n}@example.com", "password": PASSWORD},
            **extra,
        )

    def test_attempts_per_ip_are_limited(self):
        with mock.patch("accounts.views.REGISTER_IP", Rule("register-ip", 3, 3600)):
            for n in range(3):
                self.assertEqual(self.register(n).status_code, 201)
                self.client.post("/api/auth/logout/")
            blocked = self.register(99)
            self.assertEqual(blocked.status_code, 429)
            self.assertFalse(User.objects.filter(username="kisi_99").exists())
            self.assertEqual(self.register(100, REMOTE_ADDR="198.51.100.9").status_code, 201)


class PollCreateRateLimitTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ali_k", "ali@example.com", PASSWORD)
        self.other = User.objects.create_user("veli", "veli@example.com", PASSWORD)

    def create(self, n=0):
        return post(self.client, "/api/polls/", {"question": f"Soru {n}?", "options": ["A", "B"]})

    def test_five_polls_per_hour_per_user(self):
        self.client.login(username="ali_k", password=PASSWORD)
        for n in range(5):
            self.assertEqual(self.create(n).status_code, 201)
        blocked = self.create(5)
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(Poll.objects.count(), 5)
        self.client.login(username="veli", password=PASSWORD)
        self.assertEqual(self.create(6).status_code, 201)

    def test_daily_cap(self):
        daily = (Rule("poll-hour", 100, 3600), Rule("poll-day", 2, 86400))
        with mock.patch("polls.views.POLL_CREATE", daily):
            self.client.login(username="ali_k", password=PASSWORD)
            self.assertEqual(self.create(1).status_code, 201)
            self.assertEqual(self.create(2).status_code, 201)
            self.assertEqual(self.create(3).status_code, 429)

    def test_invalid_polls_do_not_use_up_the_quota(self):
        self.client.login(username="ali_k", password=PASSWORD)
        for _ in range(10):
            bad = post(self.client, "/api/polls/", {"question": "", "options": ["A"]})
            self.assertEqual(bad.status_code, 400)
        self.assertEqual(self.create().status_code, 201)

    def test_anonymous_requests_still_get_401_not_429(self):
        for _ in range(8):
            self.assertEqual(self.create().status_code, 401)


class VoteRateLimitTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user("ali_k", "ali@example.com", PASSWORD)
        self.poll, (self.a, self.b) = make_poll(self.author, "Soru")

    def vote(self, option=None, **extra):
        return post(self.client, f"/api/polls/{self.poll.id}/vote/", {"option_id": (option or self.a).id}, **extra)

    def test_anonymous_votes_are_limited_per_ip(self):
        with mock.patch("polls.views.VOTE_ANON", (Rule("vote-anon-min", 3, 60),)):
            for _ in range(3):
                self.assertEqual(self.vote().status_code, 200)
            blocked = self.vote()
            self.assertEqual(blocked.status_code, 429)
            self.assertEqual(Vote.objects.count(), 3)  # the blocked vote was not stored
            self.assertEqual(self.vote(REMOTE_ADDR="198.51.100.5").status_code, 200)

    def test_default_anonymous_limit_is_ten_per_minute(self):
        statuses = [self.vote().status_code for _ in range(11)]
        self.assertEqual(statuses, [200] * 10 + [429])

    def test_anonymous_vote_rows_carry_no_ip(self):
        self.vote(REMOTE_ADDR="203.0.113.7")
        vote = Vote.objects.get()
        self.assertIsNone(vote.user)
        self.assertEqual({f.name for f in Vote._meta.get_fields()} & {"ip", "ip_address", "remote_addr"}, set())
        self.assertFalse(RateLimitHit.objects.filter(key_hash__contains="203.0.113.7").exists())

    def test_members_are_limited_per_account_not_per_ip(self):
        with mock.patch("polls.views.VOTE_MEMBER", (Rule("vote-member-min", 2, 60),)):
            self.client.login(username="ali_k", password=PASSWORD)
            self.assertEqual(self.vote(self.a).status_code, 200)
            self.assertEqual(self.vote(self.b).status_code, 200)
            self.assertEqual(self.vote(self.a).status_code, 429)
            self.assertEqual(Vote.objects.get(user=self.author).option, self.b)

    def test_rejected_votes_do_not_count(self):
        other, (other_option, _) = make_poll(self.author, "Başka")
        for _ in range(15):
            self.assertEqual(self.vote(other_option).status_code, 400)  # wrong poll's option
        self.assertEqual(self.vote().status_code, 200)

    def test_closed_polls_answer_409_before_any_limit(self):
        Poll.objects.filter(pk=self.poll.pk).update(closed_at=timezone.now())
        for _ in range(12):
            self.assertEqual(self.vote().status_code, 409)
        self.assertEqual(RateLimitHit.objects.count(), 0)


class OptionTableUntouchedTests(TestCase):
    def test_option_model_still_has_no_tracking_fields(self):
        self.assertEqual({f.name for f in Option._meta.get_fields()}, {"id", "poll", "text", "position", "votes"})
