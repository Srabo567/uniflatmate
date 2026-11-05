"""
mess/tests.py

Run with:   python manage.py test mess

The first test is the important one. It is the regression test for the
aggregation bug described at the top of mess/models.py: without a mess
foreign key on DailyMeal and MessExpense, the meal rate was computed across
every mess on the platform at once.
"""

from datetime import date
from decimal import Decimal

from django.test import TestCase

from accounts.models import (
    Owner, Student, University, UniversityEmailDomain,
)
from listings.models import Listing
from locations.models import Area

from .models import DailyMeal, Mess, MessExpense
from .services import calculate_meal_rate, member_summary


class MealRateTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        uap = University.objects.create(
            name="University of Asia Pacific", short_code="UAP",
            latitude=23.7461, longitude=90.3742)
        UniversityEmailDomain.objects.create(
            university=uap, domain="uap-bd.edu")
        area = Area.objects.create(
            name="Farmgate", zone="C",
            latitude=23.7580, longitude=90.3896)
        owner = Owner.objects.create(username="karim", gender="M")

        common = dict(gender="F", university=uap, department="CSE",
                      batch_season="SP", batch_year=2024, roll_number="000",
                      budget=Decimal("6000"))
        cls.mim = Student.objects.create(username="mim", **common)
        cls.nabila = Student.objects.create(username="nabila", **common)
        cls.outsider = Student.objects.create(username="outsider", **common)

        def make_mess(name, listing_title, manager, members):
            listing = Listing.objects.create(
                owner=owner, area=area, title=listing_title,
                rent=Decimal("6000"), floor=2, washroom="C", furnishing="S",
                cooking="G", seats_total=4, seats_available=2,
                available_from=date(2026, 1, 1))
            mess = Mess.objects.create(
                listing=listing, manager=manager, mess_name=name)
            for m in members:
                m.mess = mess
                m.save(update_fields=["mess"])
            return mess

        cls.our_mess = make_mess("Farmgate Boys", "Flat A", cls.mim,
                                 [cls.mim, cls.nabila])
        cls.other_mess = make_mess("Someone Else", "Flat B", cls.outsider,
                                   [cls.outsider])

        # our mess: 1000 taka over 20 meals  ->  rate 50
        MessExpense.objects.create(
            mess=cls.our_mess, payer=cls.mim, amount=Decimal("1000"),
            spent_on=date(2026, 1, 5))
        DailyMeal.objects.create(
            mess=cls.our_mess, student=cls.mim, meal_date=date(2026, 1, 5),
            meal_count=Decimal("12"))
        DailyMeal.objects.create(
            mess=cls.our_mess, student=cls.nabila, meal_date=date(2026, 1, 5),
            meal_count=Decimal("8"))

        # a completely unrelated mess, with wildly different numbers
        MessExpense.objects.create(
            mess=cls.other_mess, payer=cls.outsider, amount=Decimal("90000"),
            spent_on=date(2026, 1, 5))
        DailyMeal.objects.create(
            mess=cls.other_mess, student=cls.outsider,
            meal_date=date(2026, 1, 5), meal_count=Decimal("3"))

    def test_meal_rate_is_scoped_to_one_mess(self):
        """
        THE REGRESSION TEST.

        1000 / 20 = 50. If this ever returns something near 4550, the
        .filter(mess=mess) has been dropped somewhere in services.py and the
        rate is being computed across the whole platform again.
        """
        self.assertEqual(calculate_meal_rate(self.our_mess), Decimal("50.00"))

    def test_the_other_mess_has_its_own_rate(self):
        self.assertEqual(
            calculate_meal_rate(self.other_mess), Decimal("30000.00"))

    def test_empty_mess_does_not_divide_by_zero(self):
        """The first day of the month is exactly when someone opens this."""
        listing = Listing.objects.create(
            owner=Owner.objects.first(), area=Area.objects.first(),
            title="Flat C", rent=Decimal("5000"), floor=1, washroom="C",
            furnishing="U", cooking="N", seats_total=2, seats_available=2,
            available_from=date(2026, 1, 1))
        empty = Mess.objects.create(
            listing=listing, manager=self.mim, mess_name="Brand New")
        self.assertEqual(calculate_meal_rate(empty), Decimal("0.00"))

    def test_balances_add_up(self):
        """
        mim paid 1000 and ate 12 meals (600 worth) -> +400
        nabila paid 0 and ate 8 meals (400 worth)  -> -400
        The two must cancel out, or money has appeared from nowhere.
        """
        summary = member_summary(self.our_mess)
        by_name = {r["student"].username: r for r in summary["members"]}

        self.assertEqual(by_name["mim"]["balance"], Decimal("400.00"))
        self.assertEqual(by_name["nabila"]["balance"], Decimal("-400.00"))
        self.assertEqual(
            sum(r["balance"] for r in summary["members"]), Decimal("0.00"))

    def test_summary_only_includes_this_messs_members(self):
        names = {r["student"].username
                 for r in member_summary(self.our_mess)["members"]}
        self.assertEqual(names, {"mim", "nabila"})


class MessAccessTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        uap = University.objects.create(
            name="University of Asia Pacific", short_code="UAP",
            latitude=23.7461, longitude=90.3742)
        area = Area.objects.create(
            name="Farmgate", zone="C", latitude=23.7580, longitude=90.3896)
        owner = Owner.objects.create(username="karim", gender="M")
        listing = Listing.objects.create(
            owner=owner, area=area, title="Flat A", rent=Decimal("6000"),
            floor=2, washroom="C", furnishing="S", cooking="G",
            seats_total=4, seats_available=2, available_from=date(2026, 1, 1))

        common = dict(gender="F", university=uap, department="CSE",
                      batch_season="SP", batch_year=2024, roll_number="000",
                      budget=Decimal("6000"))
        cls.manager = Student.objects.create(username="manager", **common)
        cls.member = Student.objects.create(username="member", **common)
        cls.stranger = Student.objects.create(username="stranger", **common)
        for s in (cls.manager, cls.member, cls.stranger):
            s.set_password("pw"); s.is_active = True; s.save()

        cls.mess = Mess.objects.create(
            listing=listing, manager=cls.manager, mess_name="Farmgate Boys")
        for s in (cls.manager, cls.member):
            s.mess = cls.mess
            s.save(update_fields=["mess"])

    def test_a_member_can_open_the_khata(self):
        self.client.login(username="member", password="pw")
        response = self.client.get(f"/mess/{self.mess.pk}/")
        self.assertEqual(response.status_code, 200)

    def test_a_stranger_gets_a_404_not_an_empty_page(self):
        """A mess khata is private to its own members."""
        self.client.login(username="stranger", password="pw")
        response = self.client.get(f"/mess/{self.mess.pk}/")
        self.assertEqual(response.status_code, 404)

    def test_only_the_manager_can_delete_an_entry(self):
        meal = DailyMeal.objects.create(
            mess=self.mess, student=self.member,
            meal_date=date(2026, 1, 6), meal_count=Decimal("2"))

        self.client.login(username="member", password="pw")
        self.client.post(f"/mess/{self.mess.pk}/meal/{meal.pk}/delete/")
        self.assertTrue(DailyMeal.objects.filter(pk=meal.pk).exists())

        self.client.login(username="manager", password="pw")
        self.client.post(f"/mess/{self.mess.pk}/meal/{meal.pk}/delete/")
        self.assertFalse(DailyMeal.objects.filter(pk=meal.pk).exists())

    def test_a_member_cannot_record_meals_for_someone_else(self):
        self.client.login(username="member", password="pw")
        self.client.post(f"/mess/{self.mess.pk}/meal/", {
            "student": self.manager.pk,
            "meal_date": "2026-01-07",
            "meal_count": "3",
        })
        self.assertFalse(
            DailyMeal.objects.filter(student=self.manager).exists())

    def test_the_manager_can_record_meals_for_anyone(self):
        self.client.login(username="manager", password="pw")
        self.client.post(f"/mess/{self.mess.pk}/meal/", {
            "student": self.member.pk,
            "meal_date": "2026-01-08",
            "meal_count": "2.5",
        })
        self.assertTrue(
            DailyMeal.objects.filter(student=self.member).exists())

    def test_two_entries_for_one_day_are_refused(self):
        DailyMeal.objects.create(
            mess=self.mess, student=self.member,
            meal_date=date(2026, 1, 9), meal_count=Decimal("2"))
        self.client.login(username="member", password="pw")
        self.client.post(f"/mess/{self.mess.pk}/meal/", {
            "student": self.member.pk,
            "meal_date": "2026-01-09",
            "meal_count": "3",
        })
        self.assertEqual(
            DailyMeal.objects.filter(
                student=self.member, meal_date=date(2026, 1, 9)).count(), 1)

    # --- member management (the manager role, in the product) ------------
    def test_only_the_manager_can_open_the_members_page(self):
        self.client.login(username="member", password="pw")
        r = self.client.get(f"/mess/{self.mess.pk}/members/")
        self.assertEqual(r.status_code, 302)

        self.client.login(username="manager", password="pw")
        r = self.client.get(f"/mess/{self.mess.pk}/members/")
        self.assertEqual(r.status_code, 200)

    def test_manager_can_add_a_student_with_no_mess(self):
        self.client.login(username="manager", password="pw")
        self.client.post(f"/mess/{self.mess.pk}/members/",
                         {"action": "add", "student": self.stranger.pk})
        self.stranger.refresh_from_db()
        self.assertEqual(self.stranger.mess_id, self.mess.pk)

    def test_adding_someone_from_another_mess_is_refused(self):
        """Pulling them across would orphan their meal records."""
        from listings.models import Listing
        from locations.models import Area
        from accounts.models import Owner
        other = Mess.objects.create(
            listing=Listing.objects.create(
                owner=Owner.objects.first(), area=Area.objects.first(),
                title="Flat Z", rent=Decimal("5000"), floor=1, washroom="C",
                furnishing="U", cooking="N", seats_total=1,
                seats_available=1, available_from=date(2026, 1, 1)),
            manager=self.stranger, mess_name="Other Mess")
        self.stranger.mess = other
        self.stranger.save(update_fields=["mess"])

        self.client.login(username="manager", password="pw")
        self.client.post(f"/mess/{self.mess.pk}/members/",
                         {"action": "add", "student": self.stranger.pk})
        self.stranger.refresh_from_db()
        self.assertEqual(self.stranger.mess_id, other.pk)

    def test_manager_cannot_remove_themselves(self):
        """That would leave the mess with nobody able to fix anything."""
        self.client.login(username="manager", password="pw")
        self.client.post(f"/mess/{self.mess.pk}/members/",
                         {"action": "remove", "student": self.manager.pk})
        self.manager.refresh_from_db()
        self.assertEqual(self.manager.mess_id, self.mess.pk)

    def test_removing_a_member_keeps_their_past_records(self):
        """Taking a person out must not change what everyone else owes."""
        DailyMeal.objects.create(
            mess=self.mess, student=self.member,
            meal_date=date(2026, 1, 20), meal_count=Decimal("3"))

        self.client.login(username="manager", password="pw")
        self.client.post(f"/mess/{self.mess.pk}/members/",
                         {"action": "remove", "student": self.member.pk})

        self.member.refresh_from_db()
        self.assertIsNone(self.member.mess_id)
        self.assertTrue(
            DailyMeal.objects.filter(student=self.member).exists())
