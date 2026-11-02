"""
accounts/management/commands/seed_demo.py

    python manage.py seed_demo

Fills the database with believable demo accounts so the match page has
something on it. An empty match page is the worst possible thing to put on
the projector, and creating twelve students by hand five minutes before the
viva is how people end up with everyone scoring 100%.

WHAT IT MAKES
    12 students at UAP (8 female, 4 male), deliberately spread across the
    four lifestyle answers and a range of budgets, plus 2 students at NSU
    to prove the university filter works.
    2 owners.
    4 roommate requests, in pending / accepted / declined states.

EVERY ACCOUNT USES THE SAME PASSWORD:  demo12345
and every account is already active and verified, so you can log straight
in as any of them.

SAFE TO RE-RUN. It uses get_or_create on the username, so nothing is
duplicated. `--reset` deletes the demo accounts first and starts clean.

NEVER RUN THIS ON ANYTHING REAL. It is dev-only data with a published
password. There is a guard below that refuses to run when DEBUG is False.
"""

import zlib
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import (
    Owner, RoommateRequest, Student, University,
)

PASSWORD = "demo12345"

# Marks every account this command creates, so --reset knows what to remove
# without touching the superuser you made yourself.
DEMO_TAG = "demo_"

# Phone numbers are generated below, not listed — they are only ever shown
# to an accepted connection, so the point is simply that some students have
# one and some do not.
#
# (username, gender, dept, season, year, budget, smokes, sleeps_early, study_at_home)
#
# These are chosen so the match list is INTERESTING, not so everyone agrees:
# a few near-perfect pairs, a few mid-range, and at least two that trip the
# "not recommended" warning. If every demo student is identical, the one
# feature you are presenting looks like it does nothing.
STUDENTS_UAP = [
    # female — this is the set a female account will actually see
    ("demo_nusrat",   "F", "CSE",   "SP", 2024, 6000, False, True,  True),
    ("demo_anika",    "F", "EEE",   "FA", 2023, 6500, False, True,  True),
    ("demo_tasnim",   "F", "CSE",   "SP", 2023, 7000, False, True,  False),
    ("demo_raisa",    "F", "BBA",   "FA", 2024, 5500, False, False, True),
    ("demo_meherun",  "F", "PHARM", "FA", 2023, 7200, True,  True,  False),
    ("demo_sumaiya",  "F", "CSE",   "SU", 2024, 4500, False, True,  True),
    ("demo_farzana",  "F", "ARCH",  "SP", 2022, 12000, True, True,  False),
    ("demo_rituparna", "F", "ENG",  "FA", 2024, 6200, False, True,  True),
    # male
    ("demo_shuvro",   "M", "CSE",   "SP", 2024, 6000, False, True,  True),
    ("demo_rakib",    "M", "CSE",   "FA", 2023, 5000, True,  False, False),
    ("demo_tanvir",   "M", "IPE",   "SP", 2023, 8000, False, False, True),
    ("demo_imran",    "M", "BBA",   "FA", 2024, 5800, False, True,  True),
]

STUDENTS_NSU = [
    ("demo_sadia",    "F", "BBA",   "SP", 2024, 11000, False, True, True),
    ("demo_arif",     "M", "CSE",   "FA", 2023, 10000, False, True, False),
]

OWNERS = [
    ("demo_owner_karim", "M", "01710000001"),
    ("demo_owner_nasrin", "F", "01710000002"),
]

# (sender, receiver, status, message)
REQUESTS = [
    ("demo_nusrat", "demo_anika", "P",
     "Hi! We scored high — I'm looking around Farmgate, are you?"),
    ("demo_tasnim", "demo_nusrat", "P", ""),
    ("demo_anika", "demo_sumaiya", "A", "Shall we look at a place together?"),
    ("demo_raisa", "demo_tasnim", "D", ""),
]


class Command(BaseCommand):
    help = "Create demo students, owners and roommate requests (DEBUG only)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true",
            help="Delete all demo_* accounts first, then recreate them.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        # --- guard -------------------------------------------------------
        # These accounts share one published password. Creating them on a
        # deployed site would be a real security hole, so refuse outright
        # rather than trusting whoever runs it to read the docstring.
        if not settings.DEBUG:
            raise CommandError(
                "seed_demo refuses to run with DEBUG = False. These accounts "
                "all share the password '" + PASSWORD + "' and are for local "
                "development only."
            )

        if options["reset"]:
            deleted, _ = (Student.objects.filter(username__startswith=DEMO_TAG)
                          .delete())
            Owner.objects.filter(username__startswith=DEMO_TAG).delete()
            self.stdout.write(f"Reset: removed {deleted} demo rows.")

        uap = University.objects.filter(short_code="UAP").first()
        nsu = University.objects.filter(short_code="NSU").first()
        if uap is None:
            raise CommandError(
                "No universities found. Run `python manage.py "
                "seed_universities` first."
            )

        made_students = 0
        for row in STUDENTS_UAP:
            made_students += self._student(uap, *row)
        if nsu is not None:
            for row in STUDENTS_NSU:
                made_students += self._student(nsu, *row)

        made_owners = 0
        for username, gender, phone in OWNERS:
            owner, created = Owner.objects.get_or_create(
                username=username,
                defaults={
                    "email": f"{username}@example.com",
                    "gender": gender,
                    "contact_number": phone,
                    "is_active": True,
                    "is_verified": True,
                },
            )
            if created:
                owner.set_password(PASSWORD)
                owner.save()
                made_owners += 1

        made_requests = 0
        for sender_name, receiver_name, status, message in REQUESTS:
            sender = Student.objects.filter(username=sender_name).first()
            receiver = Student.objects.filter(username=receiver_name).first()
            if sender is None or receiver is None:
                continue
            _, created = RoommateRequest.objects.get_or_create(
                sender=sender, receiver=receiver,
                defaults={"status": status, "message": message},
            )
            made_requests += int(created)

        self._listings_hint()

        self.stdout.write(self.style.SUCCESS(
            f"Demo data: {made_students} students, {made_owners} owners, "
            f"{made_requests} roommate requests."
        ))
        self.stdout.write(
            f"\nLog in as any of them with the password: {PASSWORD}\n"
            f"Try  demo_nusrat  — she has two pending requests waiting.\n"
        )

    # -----------------------------------------------------------------
    def _student(self, university, username, gender, dept, season, year,
                 budget, smokes, sleeps_early, study_at_home):
        """Create one student. Returns 1 if it was created, 0 if it existed."""
        domain = next(
            (d.domain for d in university.email_domains.all()), "example.com",
        )
        stable = zlib.crc32(username.encode())

        # Roughly two thirds of them share a phone number, so the
        # connections page shows both cases: a number, and "not shared".
        phone = "" if stable % 3 == 0 else f"017{stable % 100000000:08d}"

        student, created = Student.objects.get_or_create(
            username=username,
            defaults={
                "email": f"{username}@{domain}",
                "contact_number": phone,
                "gender": gender,
                "university": university,
                "department": dept,
                "batch_season": season,
                "batch_year": year,
                # crc32, not hash(): Python randomises string hashes per
                # process, so hash() would give a different roll number on
                # every run. Reference data should be reproducible.
                "roll_number": f"{year}{stable % 100000:05d}",
                "budget": Decimal(budget),
                "smokes": smokes,
                "sleeps_early": sleeps_early,
                "study_at_home": study_at_home,
                "is_active": True,
                "is_verified": True,
            },
        )
        if created:
            student.set_password(PASSWORD)
            student.save()
        return int(created)

    def _listings_hint(self):
        """
        Demo listings are NOT seeded here on purpose.

        This command lives in `accounts`, which belongs to one person. Demo
        listings belong to whoever owns the `listings` app, and two people
        editing one file is how a four-person project gets its first merge
        conflict. So they get their own command in their own app:

            python manage.py seed_demo_listings

        File ownership is the whole conflict-avoidance strategy. Keep it.
        """
        try:
            from listings.models import Listing  # noqa: F401
        except (ImportError, AttributeError):
            self.stdout.write(self.style.WARNING(
                "Demo listings skipped — listings/models.py has no Listing "
                "model yet."
            ))
            return

        self.stdout.write(
            "Listing model found. Run `python manage.py seed_demo_listings` "
            "for demo rooms."
        )
