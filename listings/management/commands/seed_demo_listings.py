"""
listings/management/commands/seed_demo_listings.py

    python manage.py seed_demo_listings

Demo rooms, so the owner dashboard and the search page are not empty at the
viva. Run `seed_universities`, `seed_areas`, `seed_amenities` and
`seed_demo` first — this one needs the areas, the amenities and the demo
owners those create.

WHY THIS IS NOT PART OF seed_demo
    seed_demo lives in the `accounts` app, which belongs to one person.
    This belongs to whoever owns `listings`. Two people editing one file is
    how a four-person project gets its first merge conflict — so each app
    seeds its own data.

DEV ONLY, like seed_demo: it refuses to run with DEBUG = False.

The rooms are spread deliberately: a couple within walking distance of UAP,
one further out, one female-only, one already full. A search that returns
five near-identical rooms demonstrates nothing.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Owner
from locations.models import Area

# (title, area, floor, rent, seats_total, seats_free, washroom, furnishing,
#  cooking, female_only, owner_index, amenity names)
LISTINGS = [
    ("2 seats near Farmgate, students only", "Farmgate", 3, 6000, 2, 2,
     "A", "S", "G", False, 0,
     ["Piped gas line", "Geyser (hot water)", "Refrigerator", "Lift",
      "Broadband internet", "Security guard"]),

    ("Single room, Green Road — female only", "Green Road", 2, 7000, 1, 1,
     "A", "F", "C", True, 1,
     ["Geyser (hot water)", "Air conditioner", "Refrigerator",
      "Security guard", "CCTV", "Separate entrance"]),

    ("3 seats in a shared flat, Kalabagan", "Kalabagan", 4, 4500, 3, 2,
     "C", "S", "G", False, 0,
     ["Shared kitchen", "Gas stove", "Reserve water tank",
      "Broadband internet"]),

    ("Mess seat, Azimpur — walking distance to campus", "Azimpur", 1, 4000,
     4, 1, "C", "U", "C", False, 1,
     ["Shared kitchen", "Reserve water tank", "Main road access"]),

    ("Quiet room, Shyamoli", "Shyamoli", 5, 5500, 1, 0,
     "A", "S", "I", False, 0,
     ["Induction cooker", "Refrigerator", "Lift", "Balcony",
      "Generator / IPS backup"]),

    ("2 seats, Mirpur-10 — generator and lift", "Mirpur-10", 6, 5000, 2, 2,
     "C", "S", "G", False, 1,
     ["Generator / IPS backup", "Lift", "Piped gas line", "Water filter",
      "CCTV"]),
]


class Command(BaseCommand):
    help = "Create demo listings with amenities (DEBUG only)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true",
            help="Delete the demo listings first, then recreate them.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "seed_demo_listings refuses to run with DEBUG = False. "
                "It is development data."
            )

        try:
            from listings.models import Amenity, Listing
        except ImportError:
            raise CommandError(
                "listings/models.py has no Listing model yet. Write the "
                "models, run makemigrations and migrate, then try again."
            )

        owners = list(Owner.objects.filter(username__startswith="demo_owner"))
        if not owners:
            raise CommandError(
                "No demo owners found. Run `python manage.py seed_demo` "
                "first."
            )

        if options["reset"]:
            deleted, _ = Listing.objects.filter(owner__in=owners).delete()
            self.stdout.write(f"Reset: removed {deleted} rows.")

        if not Amenity.objects.exists():
            self.stdout.write(self.style.WARNING(
                "No amenities found — run `python manage.py seed_amenities` "
                "for a fuller demo. Carrying on without them."
            ))

        made = 0
        for row in LISTINGS:
            (title, area_name, floor, rent, total, free, washroom,
             furnishing, cooking, female_only, owner_i, amenity_names) = row

            area = Area.objects.filter(name=area_name).first()
            if area is None:
                self.stdout.write(self.style.WARNING(
                    f"Skipped '{title}' — no area called {area_name}. "
                    f"Run `python manage.py seed_areas`."
                ))
                continue

            listing, created = Listing.objects.get_or_create(
                title=title,
                defaults={
                    "owner": owners[owner_i % len(owners)],
                    "area": area,
                    "rent": Decimal(rent),
                    "floor": floor,
                    "washroom": washroom,
                    "furnishing": furnishing,
                    "cooking": cooking,
                    "seats_total": total,
                    "seats_available": free,
                    "available_from": date.today() + timedelta(days=14),
                    "is_female_only": female_only,
                    # the full one is off the site, exactly as a real one
                    # would be once its last seat went
                    "is_available": free > 0,
                    "description": (
                        "Demo listing. Rent is shown as information only — "
                        "UniFlatMate records no payment."
                    ),
                },
            )
            if created:
                made += 1
                listing.amenities.set(
                    Amenity.objects.filter(name__in=amenity_names))

        self.stdout.write(self.style.SUCCESS(
            f"Demo listings: {made} added, {Listing.objects.count()} in total."
        ))
        self.stdout.write(
            "No photos — upload a few by hand through 'Post a room' so the "
            "cards are not empty grey boxes at the demo.\n"
        )
