"""Dhaka neighbourhoods — reference data several apps share.

Why its own app: a Listing sits in an area and a mess belongs to one. If
Area lived inside `listings`, then `mess` would have to import `listings`
just to name a neighbourhood. Shared reference data gets its own app.

Why not a plain text field: four people typing a name produce "Farmgate",
"farmgate", "Farm Gate" and "Fatmgate", and the area filter then misses
listings that are really there.

Rows are loaded by `python manage.py seed_areas`.
"""

from django.db import models


class Area(models.Model):
    """A neighbourhood students actually say out loud: Farmgate, Azimpur.

    The coordinates are the rough centre. They let a listing with no map
    pin still appear in a radius search, and they answer "how far is
    Mirpur-10 from UAP" before any listing exists.
    """

    class Zone(models.TextChoices):
        CENTRAL = "C", "Central Dhaka"
        NORTH = "N", "North Dhaka"
        EAST = "E", "East Dhaka"
        OLD = "O", "Old Dhaka"
        OUTER = "X", "Outer Dhaka"

    name = models.CharField(max_length=80, unique=True)
    zone = models.CharField(max_length=1, choices=Zone.choices)
    latitude = models.FloatField(help_text="Rough centre of the area")
    longitude = models.FloatField()

    is_student_hub = models.BooleanField(
        default=False,
        help_text="Areas students cluster in — shown first in the dropdown.",
    )

    class Meta:
        # student hubs first, then alphabetical, so the dropdown opens on
        # the areas most people want
        ordering = ["-is_student_hub", "name"]

    def __str__(self):
        return self.name

    def distance_to(self, university):
        """Kilometres from this area's centre to a campus.

        Reuses the same formula as the listing search. Never write the
        maths twice — change one copy and you forget the other.
        """
        from listings.services import haversine_km

        km = haversine_km(
            self.latitude, self.longitude,
            university.latitude, university.longitude,
        )
        return round(km, 2)
