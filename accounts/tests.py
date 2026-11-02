"""
accounts/tests.py  —  tests for sign-up and the roommate request flow

Run with:   python manage.py test accounts

These cover the two rules that are easy to break later:
  1. a student's email must be on their university's domain
  2. only the RECEIVER of a roommate request may answer it
"""

from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from .forms import StudentSignUpForm
from .models import (
    RoommateRequest, Student, University, UniversityEmailDomain,
)


class SignUpEmailRuleTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.uap = University.objects.create(
            name="University of Asia Pacific", short_code="UAP",
            latitude=23.7461, longitude=90.3742,
        )
        UniversityEmailDomain.objects.create(
            university=cls.uap, domain="uap-bd.edu")

        # A second university with TWO domains — the case the single
        # email_domain field could not handle.
        cls.nsu = University.objects.create(
            name="North South University", short_code="NSU",
            latitude=23.8153, longitude=90.4255,
        )
        for d in ("northsouth.edu", "northsouth.ac.bd"):
            UniversityEmailDomain.objects.create(university=cls.nsu, domain=d)

    def form_data(self, email, university=None):
        return {
            "username": "testuser", "email": email, "gender": "F",
            "university": (university or self.uap).pk, "department": "CSE",
            "batch_season": "SP", "batch_year": "2024",
            "roll_number": "24101166",
            "budget": "5000", "smokes": False, "sleeps_early": True,
            "study_at_home": True,
            "password1": "ungu3ssable-pass", "password2": "ungu3ssable-pass",
        }

    def test_university_email_is_accepted(self):
        form = StudentSignUpForm(data=self.form_data("24101166@uap-bd.edu"))
        self.assertTrue(form.is_valid(), form.errors)

    def test_personal_email_is_rejected(self):
        form = StudentSignUpForm(data=self.form_data("someone@gmail.com"))
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_either_of_a_universitys_domains_is_accepted(self):
        """The whole reason email domains became their own table."""
        for email in ("a@northsouth.edu", "b@northsouth.ac.bd"):
            data = self.form_data(email, university=self.nsu)
            data["username"] = email.split("@")[0]
            form = StudentSignUpForm(data=data)
            self.assertTrue(form.is_valid(), f"{email}: {form.errors}")

    def test_another_universitys_domain_is_rejected(self):
        """A UAP sign-up may not use an NSU address."""
        form = StudentSignUpForm(data=self.form_data("x@northsouth.edu"))
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_domain_is_normalised_on_save(self):
        d = UniversityEmailDomain.objects.create(
            university=self.uap, domain="  @Students.UAP-BD.edu ")
        d.refresh_from_db()
        self.assertEqual(d.domain, "students.uap-bd.edu")
        self.assertTrue(self.uap.allows_email("ME@STUDENTS.UAP-BD.EDU"))

    def test_new_account_starts_inactive_and_unverified(self):
        form = StudentSignUpForm(data=self.form_data("24101166@uap-bd.edu"))
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertFalse(user.is_active)
        self.assertFalse(user.is_verified)

    def test_duplicate_email_is_rejected(self):
        StudentSignUpForm(data=self.form_data("24101166@uap-bd.edu")).save()
        second = self.form_data("24101166@uap-bd.edu")
        second["username"] = "someone_else"
        form = StudentSignUpForm(data=second)
        self.assertFalse(form.is_valid())


class RoommateRequestTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        uap = University.objects.create(
            name="University of Asia Pacific", short_code="UAP",
            latitude=23.7461, longitude=90.3742,
        )
        UniversityEmailDomain.objects.create(
            university=uap, domain="uap-bd.edu")
        common = dict(gender="F", university=uap, department="CSE",
                      batch_season="SP", batch_year=2024, roll_number="000",
                      budget=Decimal("5000"))
        cls.alice = Student.objects.create(username="alice", **common)
        cls.bella = Student.objects.create(username="bella", **common)
        cls.cara = Student.objects.create(username="cara", **common)
        for u in (cls.alice, cls.bella, cls.cara):
            u.set_password("pw"); u.is_active = True; u.save()

    def test_sending_twice_creates_only_one_request(self):
        self.client.login(username="alice", password="pw")
        url = reverse("accounts:send_request", args=[self.bella.pk])
        self.client.post(url)
        self.client.post(url)
        self.assertEqual(
            RoommateRequest.objects.filter(sender=self.alice, receiver=self.bella).count(), 1
        )

    def test_get_does_not_create_a_request(self):
        """A GET must never change data."""
        self.client.login(username="alice", password="pw")
        self.client.get(reverse("accounts:send_request", args=[self.bella.pk]))
        self.assertEqual(RoommateRequest.objects.count(), 0)

    def test_only_the_receiver_can_accept(self):
        req = RoommateRequest.objects.create(sender=self.alice, receiver=self.bella)

        # cara is neither party — she must not be able to accept it
        self.client.login(username="cara", password="pw")
        self.client.post(reverse("accounts:respond_request", args=[req.pk]),
                         {"action": "accept"})
        req.refresh_from_db()
        self.assertEqual(req.status, RoommateRequest.Status.PENDING)

        # the receiver can
        self.client.login(username="bella", password="pw")
        self.client.post(reverse("accounts:respond_request", args=[req.pk]),
                         {"action": "accept"})
        req.refresh_from_db()
        self.assertEqual(req.status, RoommateRequest.Status.ACCEPTED)

    def test_cannot_request_yourself(self):
        self.client.login(username="alice", password="pw")
        self.client.post(reverse("accounts:send_request", args=[self.alice.pk]))
        self.assertEqual(RoommateRequest.objects.count(), 0)

    def test_batch_renders_as_a_readable_label(self):
        """batch_season + batch_year is stored; 'Spring 2024' is displayed."""
        self.assertEqual(self.alice.batch, "Spring 2024")
        self.assertIn("Spring 2024", self.alice.public_label)


class ContactRevealTests(TestCase):
    """
    The privacy boundary: who may see a student's phone number.

    These are the tests worth pointing at in the viva. Accepting a request
    is the ONLY thing that reveals contact details, and removing the
    connection hides them again.
    """

    @classmethod
    def setUpTestData(cls):
        uap = University.objects.create(
            name="University of Asia Pacific", short_code="UAP",
            latitude=23.7461, longitude=90.3742,
        )
        UniversityEmailDomain.objects.create(
            university=uap, domain="uap-bd.edu")
        common = dict(gender="F", university=uap, department="CSE",
                      batch_season="SP", batch_year=2024, roll_number="000",
                      budget=Decimal("5000"))
        cls.alice = Student.objects.create(
            username="alice", contact_number="01711111111", **common)
        cls.bella = Student.objects.create(
            username="bella", contact_number="01722222222", **common)
        cls.cara = Student.objects.create(
            username="cara", contact_number="01733333333", **common)
        for u in (cls.alice, cls.bella, cls.cara):
            u.set_password("pw"); u.is_active = True; u.save()

    def test_pending_request_reveals_nothing(self):
        req = RoommateRequest.objects.create(
            sender=self.alice, receiver=self.bella)
        self.assertFalse(req.contact_visible_to(self.alice))
        self.assertFalse(req.contact_visible_to(self.bella))

    def test_accepted_request_reveals_to_both_parties(self):
        req = RoommateRequest.objects.create(
            sender=self.alice, receiver=self.bella,
            status=RoommateRequest.Status.ACCEPTED)
        self.assertTrue(req.contact_visible_to(self.alice))
        self.assertTrue(req.contact_visible_to(self.bella))

    def test_declined_request_reveals_nothing(self):
        req = RoommateRequest.objects.create(
            sender=self.alice, receiver=self.bella,
            status=RoommateRequest.Status.DECLINED)
        self.assertFalse(req.contact_visible_to(self.alice))

    def test_a_third_student_never_sees_contact(self):
        """Even on an accepted request between two other people."""
        req = RoommateRequest.objects.create(
            sender=self.alice, receiver=self.bella,
            status=RoommateRequest.Status.ACCEPTED)
        self.assertFalse(req.contact_visible_to(self.cara))

    def test_phone_number_is_not_on_the_match_page(self):
        """A match card must never leak a number before anyone accepts."""
        self.client.login(username="alice", password="pw")
        html = self.client.get(reverse("matching:match_list")).content.decode()
        self.assertNotIn("01722222222", html)

    def test_connections_page_shows_the_number_only_after_accepting(self):
        self.client.login(username="alice", password="pw")
        url = reverse("accounts:connections")

        req = RoommateRequest.objects.create(
            sender=self.alice, receiver=self.bella)
        self.assertNotIn("01722222222", self.client.get(url).content.decode())

        req.status = RoommateRequest.Status.ACCEPTED
        req.save()
        self.assertIn("01722222222", self.client.get(url).content.decode())

    def test_third_party_cannot_see_it_on_their_own_page(self):
        RoommateRequest.objects.create(
            sender=self.alice, receiver=self.bella,
            status=RoommateRequest.Status.ACCEPTED)
        self.client.login(username="cara", password="pw")
        html = self.client.get(
            reverse("accounts:connections")).content.decode()
        self.assertNotIn("01711111111", html)
        self.assertNotIn("01722222222", html)

    def test_removing_a_connection_hides_contact_again(self):
        req = RoommateRequest.objects.create(
            sender=self.alice, receiver=self.bella,
            status=RoommateRequest.Status.ACCEPTED)

        # the SENDER removes it, not just the receiver
        self.client.login(username="alice", password="pw")
        self.client.post(
            reverse("accounts:remove_connection", args=[req.pk]))

        req.refresh_from_db()
        self.assertEqual(req.status, RoommateRequest.Status.DECLINED)
        self.assertFalse(req.contact_visible_to(self.alice))
        self.assertFalse(req.contact_visible_to(self.bella))

    def test_outsider_cannot_remove_someone_elses_connection(self):
        req = RoommateRequest.objects.create(
            sender=self.alice, receiver=self.bella,
            status=RoommateRequest.Status.ACCEPTED)
        self.client.login(username="cara", password="pw")
        self.client.post(
            reverse("accounts:remove_connection", args=[req.pk]))
        req.refresh_from_db()
        self.assertEqual(req.status, RoommateRequest.Status.ACCEPTED)

    def test_a_get_cannot_remove_a_connection(self):
        req = RoommateRequest.objects.create(
            sender=self.alice, receiver=self.bella,
            status=RoommateRequest.Status.ACCEPTED)
        self.client.login(username="alice", password="pw")
        self.client.get(reverse("accounts:remove_connection", args=[req.pk]))
        req.refresh_from_db()
        self.assertEqual(req.status, RoommateRequest.Status.ACCEPTED)

    def test_connections_works_in_both_directions(self):
        """Whether you sent it or received it, it is still a connection."""
        RoommateRequest.objects.create(
            sender=self.alice, receiver=self.bella,
            status=RoommateRequest.Status.ACCEPTED)
        RoommateRequest.objects.create(
            sender=self.cara, receiver=self.alice,
            status=RoommateRequest.Status.ACCEPTED)
        self.assertEqual(self.alice.connections().count(), 2)

    def test_other_party_returns_the_person_at_the_far_end(self):
        req = RoommateRequest.objects.create(
            sender=self.alice, receiver=self.bella,
            status=RoommateRequest.Status.ACCEPTED)
        self.assertEqual(req.other_party(self.alice), self.bella)
        self.assertEqual(req.other_party(self.bella), self.alice)
        self.assertIsNone(req.other_party(self.cara))


class AfterLoginTests(TestCase):
    """
    Logging in used to send everyone to /matching/, so an owner landed on
    "student profile needed" two seconds after signing in.
    """

    @classmethod
    def setUpTestData(cls):
        uap = University.objects.create(
            name="University of Asia Pacific", short_code="UAP",
            latitude=23.7461, longitude=90.3742)
        cls.student = Student.objects.create(
            username="a_student", gender="F", university=uap,
            department="CSE", batch_season="SP", batch_year=2024,
            roll_number="000", budget=Decimal("5000"))
        from .models import Owner
        cls.owner = Owner.objects.create(username="an_owner", gender="M")
        for u in (cls.student, cls.owner):
            u.set_password("pw"); u.is_active = True; u.save()

    def test_a_student_lands_on_their_matches(self):
        self.client.login(username="a_student", password="pw")
        r = self.client.get(reverse("accounts:after_login"))
        self.assertRedirects(r, reverse("matching:match_list"))

    def test_an_owner_does_not_land_on_the_student_page(self):
        """listings app যোগ হলে এটা dashboard এ যাবে। এখন profile এ।"""
        self.client.login(username="an_owner", password="pw")
        r = self.client.get(reverse("accounts:after_login"))
        self.assertRedirects(r, reverse("accounts:profile"))
