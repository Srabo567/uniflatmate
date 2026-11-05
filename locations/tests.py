"""
locations/tests.py

Run with:   python manage.py test locations
"""

from django.test import TestCase

from accounts.models import University

from .models import Area


class AreaTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.uap = University.objects.create(
            name="University of Asia Pacific", short_code="UAP",
            latitude=23.7461, longitude=90.3742,
        )
        cls.farmgate = Area.objects.create(
            name="Farmgate", zone=Area.Zone.CENTRAL,
            latitude=23.7580, longitude=90.3896, is_student_hub=True,
        )
        cls.uttara = Area.objects.create(
            name="Uttara Sector 10", zone=Area.Zone.NORTH,
            latitude=23.8760, longitude=90.3880,
        )

    def test_farmgate_is_about_two_km_from_uap(self):
        """The same number the deck quotes — worth having a test on it."""
        d = self.farmgate.distance_to(self.uap)
        self.assertTrue(1.5 < d < 2.5, f"expected roughly 2 km, got {d}")

    def test_uttara_is_much_further_than_farmgate(self):
        self.assertGreater(
            self.uttara.distance_to(self.uap),
            self.farmgate.distance_to(self.uap),
        )

    def test_student_hubs_are_listed_first(self):
        """Ordering puts hubs at the top however they were inserted."""
        names = list(Area.objects.values_list("name", flat=True))
        self.assertEqual(names[0], "Farmgate")

    def test_area_names_are_unique(self):
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Area.objects.create(
                name="Farmgate", zone=Area.Zone.CENTRAL,
                latitude=0, longitude=0,
            )
