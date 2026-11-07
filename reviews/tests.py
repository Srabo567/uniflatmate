"""
reviews/tests.py

Run with:   python manage.py test reviews

Two things matter here: a review may only be written by someone who
actually lived there, and an anonymous review must never leak a name.
"""

from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.models import (
    Owner, Student, University, UniversityEmailDomain,
)
from listings.models import Listing, SeatRequest
from locations.models import Area

from .models import Review


class ReviewTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        uap = University.objects.create(
            name="University of Asia Pacific", short_code="UAP",
            latitude=23.7461, longitude=90.3742)
        UniversityEmailDomain.objects.create(
            university=uap, domain="uap-bd.edu")
        area = Area.objects.create(
            name="Farmgate", zone="C", latitude=23.7580, longitude=90.3896)

        cls.karim = Owner.objects.create(username="karim", gender="M")
        cls.karim.set_password("pw"); cls.karim.is_active = True
        cls.karim.save()

        common = dict(gender="F", university=uap, department="CSE",
                      batch_season="SP", batch_year=2024, roll_number="000",
                      budget=Decimal("6000"))
        cls.rumana = Student.objects.create(username="rumana_k", **common)
        cls.nabila = Student.objects.create(username="nabila", **common)
        for s in (cls.rumana, cls.nabila):
            s.set_password("pw"); s.is_active = True; s.save()

        cls.listing = Listing.objects.create(
            owner=cls.karim, area=area, title="Flat A", rent=Decimal("6000"),
            floor=2, washroom="C", furnishing="S", cooking="G",
            seats_total=2, seats_available=1, available_from=date(2026, 1, 1))

        # rumana_k actually lived there; nabila never did
        SeatRequest.objects.create(
            student=cls.rumana, listing=cls.listing,
            status=SeatRequest.Status.ACCEPTED)

    # --- who may review ---------------------------------------------------
    def test_a_student_who_lived_there_can_review(self):
        self.client.login(username="rumana_k", password="pw")
        self.client.post(
            reverse("reviews:write_review", args=[self.karim.pk]),
            {"rating": 4, "comment": "Water supply was fine.",
             "is_anonymous": "on"})
        self.assertEqual(Review.objects.count(), 1)

    def test_a_student_who_never_lived_there_cannot(self):
        """Otherwise the rating means nothing at all."""
        self.client.login(username="nabila", password="pw")
        self.client.post(
            reverse("reviews:write_review", args=[self.karim.pk]),
            {"rating": 1, "comment": "Never been here.", "is_anonymous": "on"})
        self.assertEqual(Review.objects.count(), 0)

    def test_a_pending_request_is_not_enough(self):
        SeatRequest.objects.filter(student=self.rumana).update(
            status=SeatRequest.Status.PENDING)
        self.client.login(username="rumana_k", password="pw")
        self.client.post(
            reverse("reviews:write_review", args=[self.karim.pk]),
            {"rating": 5, "comment": "", "is_anonymous": "on"})
        self.assertEqual(Review.objects.count(), 0)

    def test_one_review_per_student_per_owner(self):
        Review.objects.create(author=self.rumana, owner=self.karim, rating=3)
        self.client.login(username="rumana_k", password="pw")
        self.client.post(
            reverse("reviews:write_review", args=[self.karim.pk]),
            {"rating": 5, "comment": "changed my mind", "is_anonymous": "on"})
        # the second POST edits the existing row rather than adding one
        self.assertEqual(Review.objects.count(), 1)
        self.assertEqual(Review.objects.first().rating, 5)

    # --- anonymity --------------------------------------------------------
    def test_anonymous_review_hides_the_name(self):
        review = Review.objects.create(
            author=self.rumana, owner=self.karim, rating=4, is_anonymous=True)
        self.assertEqual(review.display_name, "Anonymous")

    def test_signed_review_shows_the_name(self):
        review = Review.objects.create(
            author=self.rumana, owner=self.karim, rating=4, is_anonymous=False)
        self.assertEqual(review.display_name, "rumana_k")

    def test_the_username_is_not_in_the_page_html(self):
        """The real test — the property is useless if a template bypasses it."""
        Review.objects.create(
            author=self.rumana, owner=self.karim, rating=2,
            comment="Repairs took weeks.", is_anonymous=True)
        html = self.client.get(
            reverse("reviews:owner_reviews",
                    args=[self.karim.pk])).content.decode()
        self.assertIn("Anonymous", html)
        self.assertNotIn("rumana_k", html)

    # --- the owner's rating ----------------------------------------------
    def test_rating_updates_when_a_review_is_added(self):
        Review.objects.create(author=self.rumana, owner=self.karim, rating=4)
        Review.objects.create(author=self.nabila, owner=self.karim, rating=2)
        self.karim.refresh_from_db()
        self.assertEqual(float(self.karim.owner_rating), 3.0)

    def test_rating_goes_back_to_zero_when_the_last_review_goes(self):
        review = Review.objects.create(
            author=self.rumana, owner=self.karim, rating=5)
        self.karim.refresh_from_db()
        self.assertEqual(float(self.karim.owner_rating), 5.0)

        review.delete()
        self.karim.refresh_from_db()
        self.assertEqual(float(self.karim.owner_rating), 0.0)

    def test_review_count(self):
        Review.objects.create(author=self.rumana, owner=self.karim, rating=4)
        self.assertEqual(self.karim.review_count, 1)
