"""
mess/management/commands/seed_demo_mess.py

    python manage.py seed_demo_mess

Turns one demo listing into a working mess with members, two weeks of meal
entries and a few bazaar expenses — so the meal-rate dashboard shows real
numbers instead of zeros at the viva.

Run after: seed_universities, seed_areas, seed_amenities, seed_demo,
seed_demo_listings.

Each app seeds its own demo data. That keeps file ownership clean when
four people are working in parallel.
"""

import random
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import Student

from mess.models import DailyMeal, Mess, MessExpense

MESS_NAME = "Farmgate Shared Kitchen"

# Who eats here. These are demo students created by `seed_demo`.
MEMBERS = ["demo_nusrat", "demo_anika", "demo_sumaiya", "demo_rituparna"]
MANAGER = "demo_nusrat"

# (payer, amount, type, note, days ago)
EXPENSES = [
    (0, "3200.00", "B", "Weekly bazaar", 13),
    (1, "1850.00", "B", "Rice and oil", 11),
    (0, "900.00", "U", "Gas bill", 9),
    (2, "2400.00", "B", "Fish and vegetables", 6),
    (3, "1100.00", "B", "Eggs, milk, spices", 4),
    (1, "750.00", "O", "Cleaning and gas lighter", 2),
]


class Command(BaseCommand):
    help = "Create a demo mess with meals and expenses (DEBUG only)."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true",
                            help="Delete the demo mess first.")

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "seed_demo_mess refuses to run with DEBUG = False.")

        try:
            from listings.models import Listing
        except ImportError:
            raise CommandError("listings/models.py has no Listing model yet.")

        members = list(Student.objects.filter(username__in=MEMBERS))
        if len(members) < 2:
            raise CommandError(
                "Demo students not found. Run `python manage.py seed_demo` "
                "first.")
        members.sort(key=lambda s: MEMBERS.index(s.username))
        manager = next(s for s in members if s.username == MANAGER)

        if options["reset"]:
            Mess.objects.filter(mess_name=MESS_NAME).delete()

        listing = Listing.objects.filter(mess__isnull=True).first()
        if listing is None:
            raise CommandError(
                "No free listing to attach a mess to. Run `python manage.py "
                "seed_demo_listings` first.")

        mess, created = Mess.objects.get_or_create(
            mess_name=MESS_NAME,
            defaults={"listing": listing, "manager": manager},
        )
        if not created:
            self.stdout.write("Demo mess already exists — topping it up.")

        for student in members:
            if student.mess_id != mess.pk:
                student.mess = mess
                student.save(update_fields=["mess"])

        # --- two weeks of meals -----------------------------------------
        # Seeded random, so everyone's demo database looks the same and the
        # meal rate you rehearse with is the meal rate you present.
        rng = random.Random(24101166)
        today = timezone.localdate()
        meals_made = 0
        for day_offset in range(14, 0, -1):
            day = today - timedelta(days=day_offset)
            for student in members:
                count = rng.choice(
                    ["0", "1", "1.5", "2", "2", "2.5", "3", "0.5"])
                _, made = DailyMeal.objects.get_or_create(
                    mess=mess, student=student, meal_date=day,
                    defaults={"meal_count": Decimal(count),
                              "added_by": manager},
                )
                meals_made += int(made)

        # --- expenses ----------------------------------------------------
        expenses_made = 0
        for payer_i, amount, kind, note, days_ago in EXPENSES:
            payer = members[payer_i % len(members)]
            _, made = MessExpense.objects.get_or_create(
                mess=mess, payer=payer, note=note,
                spent_on=today - timedelta(days=days_ago),
                defaults={"amount": Decimal(amount), "expense_type": kind,
                          "added_by": manager},
            )
            expenses_made += int(made)

        from mess.services import calculate_meal_rate
        rate = calculate_meal_rate(mess)

        self.stdout.write(self.style.SUCCESS(
            f"Mess '{mess.mess_name}': {len(members)} members, "
            f"{meals_made} meal rows, {expenses_made} expenses."
        ))
        self.stdout.write(
            f"Meal rate right now: {rate} BDT per meal.\n"
            f"Log in as {MANAGER} (password demo12345) and open Meals.\n"
        )
