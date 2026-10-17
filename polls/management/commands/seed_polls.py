import random

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import User
from polls.models import Option, Poll, Vote

DEMO_USERS = ["ali_k", "zeynep", "can_m", "elif_d"]

DEMO_POLLS = [
    ("ali_k", "Bugün sinemaya mı gitsem restorana mı?", ["Sinema", "Restoran"]),
    ("zeynep", "Hafta sonu tatili için hangisi?", ["Deniz", "Dağ", "Şehir turu"]),
    ("can_m", "Akşam yemeğinde ne yesem?", ["Pizza", "Burger", "Makarna", "Kebap", "Salata"]),
    ("elif_d", "Yeni telefon alsam hangisini seçmeliyim?", ["Android", "iPhone"]),
    ("ali_k", "Sabah mı antrenman yapayım akşam mı?", ["Sabah", "Akşam", "Fark etmez"]),
    ("zeynep", "Bu dizi izlemeye değer mi?", ["Evet, hemen başla", "Hayır, vakit kaybı", "Önce bir bölüm dene"]),
]


class Command(BaseCommand):
    help = "Create demo users and polls with sample votes (demo users have no usable password)."

    def add_arguments(self, parser):
        parser.add_argument("--clear", action="store_true", help="Delete demo users and their polls, then exit.")

    @transaction.atomic
    def handle(self, *args, **options):
        if options["clear"]:
            deleted, _ = User.objects.filter(username__in=DEMO_USERS).delete()
            self.stdout.write(self.style.SUCCESS(f"Removed demo data ({deleted} rows)."))
            return

        rng = random.Random(42)
        users = {}
        for name in DEMO_USERS:
            # Created without a password, so demo accounts cannot log in.
            users[name], _ = User.objects.get_or_create(username=name, defaults={"email": f"{name}@example.com"})

        created = 0
        for author, question, texts in DEMO_POLLS:
            if Poll.objects.filter(author=users[author], question=question).exists():
                continue
            poll = Poll.objects.create(author=users[author], question=question)
            opts = [Option.objects.create(poll=poll, text=t, position=i) for i, t in enumerate(texts)]
            # Every demo user votes once, plus a few anonymous votes.
            for user in users.values():
                Vote.objects.create(poll=poll, option=rng.choice(opts), user=user)
            for _ in range(rng.randint(3, 12)):
                Vote.objects.create(poll=poll, option=rng.choice(opts), user=None)
            created += 1

        skipped = len(DEMO_POLLS) - created
        self.stdout.write(self.style.SUCCESS(f"Created {created} polls (skipped {skipped} existing)."))
