"""
matching/tests.py  —  WORKED EXAMPLE

Run with:   python manage.py test matching

Tests matter here for a specific reason: the compatibility score is the
unique feature, so "we tested it" is a much stronger answer in the viva than
"it seemed to work".
"""

from decimal import Decimal

from django.test import TestCase

from accounts.models import Student, University
from .services import BUDGET_TOLERANCE, calculate_compatibility, is_recommended


class CompatibilityScoreTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.uap = University.objects.create(
            name="University of Asia Pacific", short_code="UAP",
            latitude=23.7461, longitude=90.3742,
        )

    def make(self, name, smokes, sleeps_early, study_at_home, budget):
        return Student.objects.create(
            username=name, gender="F", university=self.uap,
            department="CSE", batch_season="SP", batch_year=2024,
            roll_number="000",
            smokes=smokes, sleeps_early=sleeps_early,
            study_at_home=study_at_home, budget=Decimal(budget),
        )

    def test_identical_students_score_100(self):
        a = self.make("a", False, True, True, "5000")
        b = self.make("b", False, True, True, "5000")
        self.assertEqual(calculate_compatibility(a, b), 100)

    def test_opposite_students_score_zero(self):
        a = self.make("a", False, True, True, "3000")
        b = self.make("b", True, False, False, "9000")
        self.assertEqual(calculate_compatibility(a, b), 0)

    def test_score_is_symmetric(self):
        """Order must never change the result."""
        a = self.make("a", True, True, False, "4000")
        b = self.make("b", False, True, True, "4500")
        self.assertEqual(
            calculate_compatibility(a, b), calculate_compatibility(b, a),
        )

    def test_budget_just_outside_tolerance_scores_nothing(self):
        a = self.make("a", False, True, True, "4000")
        far = Decimal("4000") + BUDGET_TOLERANCE + Decimal("1")
        b = self.make("b", False, True, True, str(far))
        # everything else matches, so only the budget weight is missing
        self.assertEqual(calculate_compatibility(a, b), 75)

    def test_threshold(self):
        self.assertFalse(is_recommended(30))
        self.assertTrue(is_recommended(75))
