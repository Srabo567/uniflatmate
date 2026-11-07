"""
listings/management/commands/seed_amenities.py

    python manage.py seed_amenities

Loads the amenity checklist an owner ticks when posting a room.

Same pattern as seed_universities and seed_areas: reference data lives in a
re-runnable command, not typed into the admin on four separate laptops.

This one needs listings/models.py to exist first, so it fails with a clear
message rather than a traceback if you run it too early.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

# (name, category, icon)
#
# Chosen for Dhaka student housing specifically. A geyser and a generator
# matter here in a way they would not in a template copied off the internet,
# and whether the building has a lift decides whether floor 6 is usable.
AMENITIES = [
    # utilities — the dealbreakers
    ("Piped gas line", "UTILITY", "flame"),
    ("Generator / IPS backup", "UTILITY", "bolt"),
    ("Lift", "UTILITY", "lift"),
    ("Reserve water tank", "UTILITY", "drop"),
    ("Sub-meter for electricity", "UTILITY", "meter"),
    ("Broadband internet", "UTILITY", "wifi"),

    # comfort
    ("Geyser (hot water)", "COMFORT", "geyser"),
    ("Air conditioner", "COMFORT", "ac"),
    ("Refrigerator", "COMFORT", "fridge"),
    ("Washing machine", "COMFORT", "washer"),
    ("Balcony", "COMFORT", "balcony"),
    ("Bed and almirah", "COMFORT", "bed"),
    ("Reading table", "COMFORT", "desk"),

    # kitchen
    ("Shared kitchen", "KITCHEN", "kitchen"),
    ("Gas stove", "KITCHEN", "stove"),
    ("Induction cooker", "KITCHEN", "induction"),
    ("Infrared cooker", "KITCHEN", "infrared"),
    ("Water filter", "KITCHEN", "filter"),

    # safety — these back the female-safety objective in the deck
    ("Security guard", "SAFETY", "guard"),
    ("CCTV", "SAFETY", "cctv"),
    ("Separate entrance", "SAFETY", "door"),
    ("Main road access", "SAFETY", "road"),
]


class Command(BaseCommand):
    help = "Load the amenity checklist used when posting a listing."

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            from listings.models import Amenity
        except ImportError:
            raise CommandError(
                "listings/models.py has no Amenity model yet. Write the "
                "models first (see the TODOs in that file), run "
                "makemigrations and migrate, then run this again."
            )

        created = 0
        for name, category, icon in AMENITIES:
            _, made = Amenity.objects.get_or_create(
                name=name,
                defaults={"category": category, "icon": icon},
            )
            created += int(made)

        self.stdout.write(self.style.SUCCESS(
            f"Amenities: {created} added, {Amenity.objects.count()} in total."
        ))
