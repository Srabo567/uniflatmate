"""
locations/models.py  —  reference data, written and owned by nobody's module

One tiny model: Area. A Dhaka neighbourhood.

WHY THIS IS ITS OWN APP
    Area is shared. A Listing sits in an area, a search filters by area, and
    later a mess belongs to one. If it lived inside `listings`, then `mess`
    would have to import from `listings` to mention a neighbourhood, which
    couples two modules that should not know about each other.

    Reference data that several apps need belongs in an app of its own. That
    is the whole rule, and it is a good answer if Sir asks why there are six
    apps instead of five.

WHY NOT JUST A CharField ON Listing
    Exactly the reason department stopped being free text. Four people
    typing a neighbourhood produce "Farmgate", "farmgate", "Farm Gate" and
    "Fatmgate", and the area filter then misses listings that are really
    there. A foreign key makes that impossible.

Rows are loaded by `python manage.py seed_areas`.
"""

from django.db import models


class Area(models.Model):
    """
    A neighbourhood students actually say out loud: Farmgate, Azimpur,
    Mirpur-10.

    The coordinates are the rough centre of the area. Two uses:

      1. A listing whose owner has not dropped a map pin yet can fall back
         to its area's centre, so it still appears in a radius search
         instead of vanishing.
      2. "How far is Mirpur-10 from UAP?" is answerable without any
         listings existing at all — handy while you are still building.
    """

    class Zone(models.TextChoices):
        """Rough side of the city. Only used for grouping the dropdown."""
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
        help_text="Areas students actually cluster in — shown first in the "
                  "dropdown. Not a judgement about the area, just a default.",
    )

    class Meta:
        # student hubs first, then alphabetical — so the dropdown opens on
        # the areas most people want instead of on whatever starts with 'A'
        ordering = ["-is_student_hub", "name"]

    def __str__(self):
        return self.name

    def distance_to(self, university):
        """
        Kilometres from this area's centre to a campus.

        Reuses the same haversine as the listing search — one implementation
        of the maths, used everywhere. Never write the formula twice.
        """
        from listings.services import haversine_km
        return round(haversine_km(
            self.latitude, self.longitude,
            university.latitude, university.longitude,
        ), 2)
