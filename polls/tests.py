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


class VoteApiTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user("ali_k", "ali@example.com", "kedi-masa-2026")
        self.poll, (self.yes, self.no) = make_poll(self.author, "Soru")

    def vote(self, option_id, poll=None, client=None):
        import json

        poll = poll or self.poll
        return (client or self.client).post(
            f"/api/polls/{poll.id}/vote/",
            data=json.dumps({"option_id": option_id}),
            content_type="application/json",
        )

    def test_anonymous_vote_is_stored_without_a_user(self):
        response = self.vote(self.yes.id)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total_votes"], 1)
        self.assertEqual(body["options"][0]["percent"], 100)
        self.assertIsNone(body["my_vote"])
        self.assertEqual(Vote.objects.get().user, None)

    def test_logged_in_vote_and_change(self):
        self.client.login(username="ali_k", password="kedi-masa-2026")
        first = self.vote(self.yes.id).json()
        self.assertEqual(first["my_vote"], self.yes.id)
        second = self.vote(self.no.id).json()
        self.assertEqual(second["my_vote"], self.no.id)
        self.assertEqual(second["total_votes"], 1)
        self.assertEqual(Vote.objects.filter(user=self.author).count(), 1)
        self.assertEqual([o["votes"] for o in second["options"]], [0, 1])

    def test_option_must_belong_to_the_poll(self):
        other, (other_yes, _) = make_poll(self.author, "Başka soru")
        self.assertEqual(self.vote(other_yes.id).status_code, 400)
        self.assertEqual(Vote.objects.count(), 0)

    def test_invalid_option_ids_are_rejected(self):
        for value in (None, "abc", True, 999999, [1]):
            self.assertEqual(self.vote(value).status_code, 400, value)

    def test_unknown_poll_and_wrong_method(self):
        class Missing:
            id = 999999

        self.assertEqual(self.vote(self.yes.id, poll=Missing()).status_code, 404)
        self.assertEqual(self.client.get(f"/api/polls/{self.poll.id}/vote/").status_code, 405)

    def test_csrf_is_enforced(self):
        from django.test import Client

        strict = Client(enforce_csrf_checks=True)
        self.assertEqual(self.vote(self.yes.id, client=strict).status_code, 403)


class PollCreateTests(TestCase):
    URL = "/api/polls/"

    def setUp(self):
        self.user = User.objects.create_user("ali_k", "ali-private@example.com", "kedi-masa-2026")

    def create(self, **overrides):
        import json

        payload = {"question": "Sinema mi restoran mı?", "options": ["Sinema", "Restoran"]}
        payload.update(overrides)
        return self.client.post(self.URL, data=json.dumps(payload), content_type="application/json")

    def login(self):
        self.client.login(username="ali_k", password="kedi-masa-2026")

    def test_anonymous_gets_401_and_nothing_is_created(self):
        self.assertEqual(self.create().status_code, 401)
        self.assertEqual(Poll.objects.count(), 0)

    def test_create_returns_poll_in_order_with_author_and_no_email(self):
        self.login()
        response = self.create(question="  Soru?  ", options=[" B ", "A", "C"])
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["question"], "Soru?")
        self.assertEqual(body["author"], "ali_k")
        self.assertEqual([o["text"] for o in body["options"]], ["B", "A", "C"])
        self.assertEqual(body["total_votes"], 0)
        self.assertNotIn("ali-private@example.com", response.content.decode())
        # and it shows up at the top of the feed
        self.assertEqual(self.client.get(self.URL).json()["polls"][0]["id"], body["id"])

    def test_option_count_bounds(self):
        self.login()
        for count, expected in ((0, 400), (1, 400), (2, 201), (5, 201), (6, 400)):
            response = self.create(options=[f"Seçenek {i}" for i in range(count)])
            self.assertEqual(response.status_code, expected, count)
            if expected == 400:
                self.assertIn("options", response.json()["errors"])
        self.assertEqual(Poll.objects.count(), 2)

    def test_invalid_content_is_rejected_atomically(self):
        self.login()
        bad_payloads = [
            {"question": "   "},
            {"question": "x" * 141},
            {"options": ["A", "  "]},
            {"options": ["A", "a"]},
            {"options": ["A", "x" * 61]},
            {"options": ["A", 5]},
            {"options": "A,B"},
            {"question": None},
        ]
        for payload in bad_payloads:
            self.assertEqual(self.create(**payload).status_code, 400, payload)
        self.assertEqual(Poll.objects.count(), 0)
        self.assertEqual(Option.objects.count(), 0)

    def test_limits_are_inclusive(self):
        self.login()
        response = self.create(question="x" * 140, options=["a" * 60, "b"])
        self.assertEqual(response.status_code, 201)

    def test_malformed_body(self):
        self.login()
        response = self.client.post(self.URL, data="nope", content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_csrf_is_enforced(self):
        import json

        from django.test import Client

        strict = Client(enforce_csrf_checks=True)
        strict.login(username="ali_k", password="kedi-masa-2026")
        response = strict.post(self.URL, data=json.dumps({}), content_type="application/json")
        self.assertEqual(response.status_code, 403)

    def test_create_page_requires_login(self):
        response = self.client.get("/olustur/")
        self.assertRedirects(response, "/giris/?next=/olustur/", fetch_redirect_response=False)
        self.login()
        self.assertEqual(self.client.get("/olustur/").status_code, 200)

    def test_put_not_allowed(self):
        self.assertEqual(self.client.put(self.URL).status_code, 405)


class PollDeleteAndPageTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user("ali_k", "ali@example.com", "kedi-masa-2026")
        self.other = User.objects.create_user("veli", "veli@example.com", "kedi-masa-2026")
        self.poll, (self.yes, _) = make_poll(self.author, "Silinecek mi?")
        Vote.objects.create(poll=self.poll, option=self.yes, user=self.other)

    def url(self, poll=None):
        return f"/api/polls/{(poll or self.poll).id}/"

    def test_anonymous_cannot_delete(self):
        self.assertEqual(self.client.delete(self.url()).status_code, 401)
        self.assertTrue(Poll.objects.filter(pk=self.poll.pk).exists())

    def test_non_author_cannot_delete(self):
        self.client.login(username="veli", password="kedi-masa-2026")
        self.assertEqual(self.client.delete(self.url()).status_code, 403)
        self.assertTrue(Poll.objects.filter(pk=self.poll.pk).exists())

    def test_author_deletes_poll_with_options_and_votes(self):
        self.client.login(username="ali_k", password="kedi-masa-2026")
        self.assertEqual(self.client.delete(self.url()).status_code, 204)
        self.assertEqual(Poll.objects.count(), 0)
        self.assertEqual(Option.objects.count(), 0)
        self.assertEqual(Vote.objects.count(), 0)
        self.assertEqual(self.client.get(self.url()).status_code, 404)

    def test_delete_missing_poll_is_json_404(self):
        self.client.login(username="ali_k", password="kedi-masa-2026")
        response = self.client.delete("/api/polls/999999/")
        self.assertEqual(response.status_code, 404)
        self.assertIn("errors", response.json())

    def test_delete_requires_csrf(self):
        from django.test import Client

        strict = Client(enforce_csrf_checks=True)
        strict.login(username="ali_k", password="kedi-masa-2026")
        self.assertEqual(strict.delete(self.url()).status_code, 403)
        self.assertTrue(Poll.objects.filter(pk=self.poll.pk).exists())

    def test_poll_page_renders_and_escapes_question(self):
        poll, _ = make_poll(self.author, "<script>alert(1)</script>?")
        response = self.client.get(f"/anket/{poll.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")

    def test_missing_poll_page_and_unknown_url_use_the_404_template(self):
        for url in ("/anket/999999/", "/boyle-bir-sayfa/"):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 404)
            self.assertContains(response, "Bu sayfa bulunamadı", status_code=404)


class PollSortTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user("ali_k", "ali@example.com", "kedi-masa-2026")

    def questions(self, query=""):
        return [p["question"] for p in self.client.get("/api/polls/" + query).json()["polls"]]

    def test_popular_sorts_by_votes_then_newest(self):
        quiet, _ = make_poll(self.author, "Sessiz", age_minutes=1)
        busy, (yes, _) = make_poll(self.author, "Kalabalık", age_minutes=50)
        mid, (mid_yes, _) = make_poll(self.author, "Orta", age_minutes=30)
        for _ in range(3):
            Vote.objects.create(poll=busy, option=yes)
        Vote.objects.create(poll=mid, option=mid_yes)
        self.assertEqual(self.questions(), ["Sessiz", "Orta", "Kalabalık"])
        self.assertEqual(self.questions("?sort=popular"), ["Kalabalık", "Orta", "Sessiz"])

    def test_unknown_sort_falls_back_to_newest(self):
        make_poll(self.author, "Eski", age_minutes=10)
        make_poll(self.author, "Yeni", age_minutes=1)
        self.assertEqual(self.questions("?sort=bogus"), ["Yeni", "Eski"])

    def test_popular_keeps_query_count_constant(self):
        for i in range(10):
            poll, options = make_poll(self.author, f"Soru {i}")
            Vote.objects.create(poll=poll, option=options[0])
        with self.assertNumQueries(2):
            self.client.get("/api/polls/?sort=popular")
