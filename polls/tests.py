from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import User

from .models import Option, Poll, Vote


def make_poll(author, question, texts=("Evet", "Hayır"), age_minutes=0):
    poll = Poll.objects.create(author=author, question=question)
    Poll.objects.filter(pk=poll.pk).update(created_at=timezone.now() - timedelta(minutes=age_minutes))
    options = [Option.objects.create(poll=poll, text=t, position=i) for i, t in enumerate(texts)]
    return poll, options


class PollApiTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user("ali_k", "ali-private@example.com", "kedi-masa-2026")

    def test_list_is_newest_first_with_counts_and_percentages(self):
        make_poll(self.author, "Eski", age_minutes=60)
        new, (yes, no) = make_poll(self.author, "Yeni", age_minutes=1)
        for option in (yes, yes, yes, no):
            Vote.objects.create(poll=new, option=option)
        data = self.client.get("/api/polls/").json()
        self.assertEqual([p["question"] for p in data["polls"]], ["Yeni", "Eski"])
        first = data["polls"][0]
        self.assertEqual(first["total_votes"], 4)
        self.assertEqual(
            [(o["text"], o["votes"], o["percent"]) for o in first["options"]],
            [("Evet", 3, 75), ("Hayır", 1, 25)],
        )
        self.assertEqual(first["author"], "ali_k")
        self.assertEqual(data["polls"][1]["total_votes"], 0)
        self.assertEqual(data["polls"][1]["options"][0]["percent"], 0)

    def test_pagination(self):
        for i in range(12):
            make_poll(self.author, f"Soru {i}", age_minutes=100 - i)
        page1 = self.client.get("/api/polls/").json()
        page2 = self.client.get("/api/polls/?page=2").json()
        self.assertEqual(len(page1["polls"]), 10)
        self.assertTrue(page1["has_next"])
        self.assertEqual(len(page2["polls"]), 2)
        self.assertFalse(page2["has_next"])
        self.assertEqual(self.client.get("/api/polls/?page=abc").json()["page"], 1)

    def test_no_n_plus_one_queries(self):
        for i in range(10):
            poll, options = make_poll(self.author, f"Soru {i}", texts=("a", "b", "c"))
            Vote.objects.create(poll=poll, option=options[0])
        # polls + options, independent of how many polls are on the page
        with self.assertNumQueries(2):
            self.client.get("/api/polls/")
        self.client.login(username="ali_k", password="kedi-masa-2026")
        # session + user + polls + options + my votes
        with self.assertNumQueries(5):
            self.client.get("/api/polls/")

    def test_email_is_never_exposed(self):
        poll, _ = make_poll(self.author, "Soru")
        for url in ("/api/polls/", f"/api/polls/{poll.id}/"):
            self.assertNotIn("ali-private@example.com", self.client.get(url).content.decode())

    def test_detail_and_404(self):
        poll, _ = make_poll(self.author, "Soru")
        self.assertEqual(self.client.get(f"/api/polls/{poll.id}/").json()["question"], "Soru")
        self.assertEqual(self.client.get("/api/polls/999999/").status_code, 404)

    def test_my_vote_only_for_logged_in_user(self):
        poll, (yes, _) = make_poll(self.author, "Soru")
        Vote.objects.create(poll=poll, option=yes, user=self.author)
        Vote.objects.create(poll=poll, option=yes)  # anonymous
        self.assertIsNone(self.client.get(f"/api/polls/{poll.id}/").json()["my_vote"])
        self.client.login(username="ali_k", password="kedi-masa-2026")
        self.assertEqual(self.client.get(f"/api/polls/{poll.id}/").json()["my_vote"], yes.id)
        self.assertEqual(self.client.get("/api/polls/").json()["polls"][0]["my_vote"], yes.id)
