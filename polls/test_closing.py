import json
from datetime import timedelta

from django.test import Client, TestCase
from django.utils import timezone

from accounts.models import User

from .models import POLL_LIFETIME, Poll, Vote
from .tests import make_poll

PASSWORD = "kedi-masa-2026"


def age(poll, **delta):
    """Pretend the poll was created `delta` ago."""
    Poll.objects.filter(pk=poll.pk).update(created_at=timezone.now() - timedelta(**delta))
    poll.refresh_from_db()


class ClosedStateTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user("ali_k", "ali@example.com", PASSWORD)

    def test_poll_lifetime_is_two_hours(self):
        self.assertEqual(POLL_LIFETIME, timedelta(hours=2))

    def test_fresh_poll_is_open_and_reports_its_deadline(self):
        poll, _ = make_poll(self.author, "Açık")
        body = self.client.get(f"/api/polls/{poll.id}/").json()
        self.assertFalse(body["is_closed"])
        self.assertIsNotNone(body["closes_at"])

    def test_poll_closes_automatically_after_two_hours(self):
        poll, _ = make_poll(self.author, "Eski")
        age(poll, hours=1, minutes=59)
        self.assertFalse(poll.is_closed)
        age(poll, hours=2, seconds=1)
        self.assertTrue(poll.is_closed)
        body = self.client.get(f"/api/polls/{poll.id}/").json()
        self.assertTrue(body["is_closed"])
        self.assertIsNone(body["closes_at"])

    def test_manually_closed_poll_is_closed_before_the_deadline(self):
        poll, _ = make_poll(self.author, "Erken kapandı")
        Poll.objects.filter(pk=poll.pk).update(closed_at=timezone.now())
        self.assertTrue(Poll.objects.get(pk=poll.pk).is_closed)

    def test_closed_tab_lists_only_closed_polls_and_other_tabs_list_all(self):
        open_poll, _ = make_poll(self.author, "Açık")
        auto, _ = make_poll(self.author, "Süresi doldu")
        age(auto, hours=3)
        manual, _ = make_poll(self.author, "Elle kapatıldı")
        Poll.objects.filter(pk=manual.pk).update(closed_at=timezone.now())

        def listing(query=""):
            data = self.client.get("/api/polls/" + query).json()["polls"]
            return {p["question"]: p["is_closed"] for p in data}

        self.assertEqual(listing("?status=closed"), {"Süresi doldu": True, "Elle kapatıldı": True})
        self.assertEqual(
            listing(), {"Açık": False, "Süresi doldu": True, "Elle kapatıldı": True}
        )
        self.assertEqual(len(listing("?sort=popular")), 3)

    def test_closed_filter_keeps_query_count_constant(self):
        for i in range(10):
            poll, _ = make_poll(self.author, f"Soru {i}")
            age(poll, hours=3)
        with self.assertNumQueries(2):
            self.client.get("/api/polls/?status=closed")


class VoteOnClosedPollTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user("ali_k", "ali@example.com", PASSWORD)
        self.poll, (self.yes, self.no) = make_poll(self.author, "Soru")

    def vote(self, option, client=None):
        return (client or self.client).post(
            f"/api/polls/{self.poll.id}/vote/",
            data=json.dumps({"option_id": option.id}),
            content_type="application/json",
        )

    def test_voting_is_rejected_after_the_automatic_deadline(self):
        age(self.poll, hours=2, minutes=1)
        response = self.vote(self.yes)
        self.assertEqual(response.status_code, 409)
        body = response.json()
        self.assertIn("errors", body)
        self.assertTrue(body["poll"]["is_closed"])  # lets the client redraw the card
        self.assertEqual(Vote.objects.count(), 0)

    def test_voting_is_rejected_after_the_author_closed_it(self):
        Poll.objects.filter(pk=self.poll.pk).update(closed_at=timezone.now())
        self.assertEqual(self.vote(self.yes).status_code, 409)
        self.assertEqual(Vote.objects.count(), 0)

    def test_member_cannot_change_vote_once_closed(self):
        self.client.login(username="ali_k", password=PASSWORD)
        self.assertEqual(self.vote(self.yes).status_code, 200)
        Poll.objects.filter(pk=self.poll.pk).update(closed_at=timezone.now())
        response = self.vote(self.no)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["poll"]["my_vote"], self.yes.id)
        self.assertEqual(Vote.objects.get().option, self.yes)

    def test_open_poll_still_accepts_votes_just_before_the_deadline(self):
        age(self.poll, hours=1, minutes=59)
        self.assertEqual(self.vote(self.yes).status_code, 200)


class ClosePollEndpointTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user("ali_k", "ali@example.com", PASSWORD)
        self.other = User.objects.create_user("veli", "veli@example.com", PASSWORD)
        self.poll, _ = make_poll(self.author, "Soru")
        self.url = f"/api/polls/{self.poll.id}/close/"

    def test_anonymous_gets_401(self):
        self.assertEqual(self.client.post(self.url).status_code, 401)
        self.assertIsNone(Poll.objects.get(pk=self.poll.pk).closed_at)

    def test_non_author_gets_403(self):
        self.client.login(username="veli", password=PASSWORD)
        self.assertEqual(self.client.post(self.url).status_code, 403)
        self.assertIsNone(Poll.objects.get(pk=self.poll.pk).closed_at)

    def test_author_closes_the_poll(self):
        self.client.login(username="ali_k", password=PASSWORD)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["is_closed"])
        self.assertIsNotNone(Poll.objects.get(pk=self.poll.pk).closed_at)

    def test_closing_twice_keeps_the_first_close_time(self):
        self.client.login(username="ali_k", password=PASSWORD)
        self.client.post(self.url)
        first = Poll.objects.get(pk=self.poll.pk).closed_at
        self.assertEqual(self.client.post(self.url).status_code, 200)
        self.assertEqual(Poll.objects.get(pk=self.poll.pk).closed_at, first)

    def test_closing_an_expired_poll_is_a_no_op(self):
        age(self.poll, hours=3)
        self.client.login(username="ali_k", password=PASSWORD)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(Poll.objects.get(pk=self.poll.pk).closed_at)

    def test_missing_poll_wrong_method_and_csrf(self):
        self.client.login(username="ali_k", password=PASSWORD)
        self.assertEqual(self.client.post("/api/polls/999999/close/").status_code, 404)
        self.assertEqual(self.client.get(self.url).status_code, 405)
        strict = Client(enforce_csrf_checks=True)
        strict.login(username="ali_k", password=PASSWORD)
        self.assertEqual(strict.post(self.url).status_code, 403)
        self.assertIsNone(Poll.objects.get(pk=self.poll.pk).closed_at)

    def test_author_can_still_delete_a_closed_poll(self):
        self.client.login(username="ali_k", password=PASSWORD)
        self.client.post(self.url)
        self.assertEqual(self.client.delete(f"/api/polls/{self.poll.id}/").status_code, 204)
