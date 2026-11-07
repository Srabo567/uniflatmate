"""
listings/tests.py  —  WORKED EXAMPLE

Run with:   python manage.py test listings

These test the distance maths only, so they need no database rows — which
is exactly why the logic lives in services.py and not in a view.
"""

from django.test import SimpleTestCase

from .services import bounding_box, haversine_km

UAP = (23.7461, 90.3742)        # University of Asia Pacific, Dhanmondi
FARMGATE = (23.7580, 90.3896)   # Farmgate


class HaversineTests(SimpleTestCase):

    def test_distance_to_itself_is_zero(self):
        self.assertAlmostEqual(haversine_km(*UAP, *UAP), 0.0, places=6)

    def test_uap_to_farmgate_is_about_two_km(self):
        d = haversine_km(*UAP, *FARMGATE)
        self.assertTrue(1.5 < d < 2.5, f"expected roughly 2 km, got {d:.2f}")

    def test_distance_is_symmetric(self):
        self.assertAlmostEqual(
            haversine_km(*UAP, *FARMGATE), haversine_km(*FARMGATE, *UAP),
            places=9,
        )


class BoundingBoxTests(SimpleTestCase):

    def test_box_contains_the_centre(self):
        box = bounding_box(*UAP, 3)
        self.assertTrue(box["lat_min"] < UAP[0] < box["lat_max"])
        self.assertTrue(box["lon_min"] < UAP[1] < box["lon_max"])

    def test_box_is_wider_in_longitude_than_latitude(self):
        """Longitude degrees are shorter this far from the equator, so the
        box must span MORE degrees of longitude to cover the same km."""
        box = bounding_box(*UAP, 3)
        self.assertGreater(box["lon_max"] - box["lon_min"],
                           box["lat_max"] - box["lat_min"])

    def test_box_never_excludes_a_point_inside_the_radius(self):
        """The box over-includes by design; it must never under-include."""
        box = bounding_box(*UAP, 3)
        east_lon = UAP[1] + 2.9 / (111.0 * 0.9155)   # 2.9 km due east
        self.assertLessEqual(east_lon, box["lon_max"])


# =========================================================================
#  Owner-side tests
#
#  These need listings/models.py to exist AND the listings route to be
#  uncommented in uniflatmate/urls.py. Until then they skip with a reason
#  instead of failing, so `manage.py test` stays green while that work is
#  outstanding. They switch themselves on the moment both are done.
# =========================================================================

import unittest
from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import NoReverseMatch, reverse


def _ready():
    try:
        from .models import Listing, SeatRequest          # noqa: F401
    except ImportError:
        return False, "listings/models.py not written yet"
    try:
        reverse("listings:search")
    except NoReverseMatch:
        return False, "listings route still commented out in uniflatmate/urls.py"
    return True, ""


READY, SKIP_REASON = _ready()


@unittest.skipUnless(READY, SKIP_REASON)
class OwnerListingTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        from accounts.models import (
            Owner, Student, University, UniversityEmailDomain,
        )
        from locations.models import Area
        from .models import Listing

        cls.uap = University.objects.create(
            name="University of Asia Pacific", short_code="UAP",
            latitude=23.7461, longitude=90.3742,
        )
        UniversityEmailDomain.objects.create(
            university=cls.uap, domain="uap-bd.edu")
        cls.farmgate = Area.objects.create(
            name="Farmgate", zone="C",
            latitude=23.7580, longitude=90.3896, is_student_hub=True)

        cls.karim = Owner.objects.create(
            username="karim", gender="M", contact_number="01700000001")
        cls.nasrin = Owner.objects.create(
            username="nasrin", gender="F", contact_number="01700000002")
        for o in (cls.karim, cls.nasrin):
            o.set_password("pw"); o.is_active = True; o.save()

        student = dict(gender="F", university=cls.uap, department="CSE",
                       batch_season="SP", batch_year=2024, roll_number="000",
                       budget=Decimal("6000"))
        cls.mim = Student.objects.create(
            username="mim", contact_number="01811111111", **student)
        student_m = dict(student, gender="M")
        cls.rakib = Student.objects.create(username="rakib", **student_m)
        for s in (cls.mim, cls.rakib):
            s.set_password("pw"); s.is_active = True; s.save()

        cls.listing = Listing.objects.create(
            owner=cls.karim, area=cls.farmgate, title="2 seats near Farmgate",
            rent=Decimal("6000"), floor=3, washroom="A", furnishing="S",
            cooking="G", seats_total=2, seats_available=2,
            available_from=date(2026, 1, 1),
        )
        cls.female_only = Listing.objects.create(
            owner=cls.nasrin, area=cls.farmgate, title="Female-only seat",
            rent=Decimal("7000"), floor=2, washroom="C", furnishing="S",
            cooking="C", seats_total=1, seats_available=1,
            available_from=date(2026, 1, 1), is_female_only=True,
        )

    # --- coordinates -----------------------------------------------------
    def test_listing_without_a_pin_falls_back_to_its_area(self):
        """Otherwise it silently never appears in any radius search."""
        self.assertAlmostEqual(self.listing.latitude, self.farmgate.latitude)
        self.assertAlmostEqual(self.listing.longitude, self.farmgate.longitude)

    # --- the security filter ---------------------------------------------
    def test_female_only_listing_is_hidden_from_male_students(self):
        from .models import Listing
        visible = Listing.visible_to(self.rakib).values_list("pk", flat=True)
        self.assertIn(self.listing.pk, visible)
        self.assertNotIn(self.female_only.pk, visible)

    def test_female_only_listing_is_visible_to_female_students(self):
        from .models import Listing
        visible = Listing.visible_to(self.mim).values_list("pk", flat=True)
        self.assertIn(self.female_only.pk, visible)

    def test_female_only_detail_page_is_404_not_a_blank_page(self):
        self.client.login(username="rakib", password="pw")
        response = self.client.get(
            reverse("listings:detail", args=[self.female_only.pk]))
        self.assertEqual(response.status_code, 404)

    # --- ownership -------------------------------------------------------
    def test_an_owner_cannot_edit_someone_elses_listing(self):
        self.client.login(username="nasrin", password="pw")
        response = self.client.get(
            reverse("listings:edit", args=[self.listing.pk]))
        self.assertEqual(response.status_code, 404)

    def test_a_student_cannot_open_the_owner_dashboard(self):
        self.client.login(username="mim", password="pw")
        response = self.client.get(reverse("listings:dashboard"))
        self.assertEqual(response.status_code, 302)

    # --- seat requests ---------------------------------------------------
    def test_a_get_does_not_create_a_seat_request(self):
        from .models import SeatRequest
        self.client.login(username="mim", password="pw")
        self.client.get(reverse("listings:request_seat", args=[self.listing.pk]))
        self.assertEqual(SeatRequest.objects.count(), 0)

    def test_requesting_twice_creates_only_one_row(self):
        from .models import SeatRequest
        self.client.login(username="mim", password="pw")
        url = reverse("listings:request_seat", args=[self.listing.pk])
        self.client.post(url, {"message": "hello"})
        self.client.post(url, {"message": "hello again"})
        self.assertEqual(SeatRequest.objects.count(), 1)

    def test_accepting_takes_one_seat_off_the_listing(self):
        from .models import SeatRequest
        req = SeatRequest.objects.create(student=self.mim, listing=self.listing)
        self.client.login(username="karim", password="pw")
        self.client.post(
            reverse("listings:respond_seat_request", args=[req.pk]),
            {"action": "accept"})
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.seats_available, 1)

    def test_last_seat_taken_closes_the_listing(self):
        from .models import SeatRequest
        self.listing.seats_available = 1
        self.listing.save()
        req = SeatRequest.objects.create(student=self.mim, listing=self.listing)
        self.client.login(username="karim", password="pw")
        self.client.post(
            reverse("listings:respond_seat_request", args=[req.pk]),
            {"action": "accept"})
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.seats_available, 0)
        self.assertFalse(self.listing.is_available)

    def test_only_the_listings_owner_can_respond(self):
        from .models import SeatRequest
        req = SeatRequest.objects.create(student=self.mim, listing=self.listing)
        self.client.login(username="nasrin", password="pw")
        self.client.post(
            reverse("listings:respond_seat_request", args=[req.pk]),
            {"action": "accept"})
        req.refresh_from_db()
        self.assertEqual(req.status, SeatRequest.Status.PENDING)

    # --- contact reveal --------------------------------------------------
    def test_owner_phone_is_hidden_while_pending(self):
        from .models import SeatRequest
        SeatRequest.objects.create(student=self.mim, listing=self.listing)
        self.client.login(username="mim", password="pw")
        html = self.client.get(
            reverse("listings:detail", args=[self.listing.pk])).content.decode()
        self.assertNotIn("01700000001", html)

    def test_owner_phone_appears_once_accepted(self):
        from .models import SeatRequest
        SeatRequest.objects.create(
            student=self.mim, listing=self.listing,
            status=SeatRequest.Status.ACCEPTED)
        self.client.login(username="mim", password="pw")
        html = self.client.get(
            reverse("listings:detail", args=[self.listing.pk])).content.decode()
        self.assertIn("01700000001", html)

    def test_student_phone_is_hidden_from_the_owner_while_pending(self):
        from .models import SeatRequest
        SeatRequest.objects.create(student=self.mim, listing=self.listing)
        self.client.login(username="karim", password="pw")
        html = self.client.get(
            reverse("listings:seat_requests")).content.decode()
        self.assertNotIn("01811111111", html)

    def test_student_phone_appears_to_the_owner_once_accepted(self):
        from .models import SeatRequest
        SeatRequest.objects.create(
            student=self.mim, listing=self.listing,
            status=SeatRequest.Status.ACCEPTED)
        self.client.login(username="karim", password="pw")
        html = self.client.get(
            reverse("listings:seat_requests")).content.decode()
        self.assertIn("01811111111", html)

    def test_an_unrelated_owner_never_sees_the_students_phone(self):
        from .models import SeatRequest
        SeatRequest.objects.create(
            student=self.mim, listing=self.listing,
            status=SeatRequest.Status.ACCEPTED)
        self.client.login(username="nasrin", password="pw")
        html = self.client.get(
            reverse("listings:seat_requests")).content.decode()
        self.assertNotIn("01811111111", html)
