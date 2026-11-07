"""Universities, users, students, owners, and roommate requests."""

from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q


class University(models.Model):
    """One campus. Coordinates make "within 3 km of my campus" possible."""

    name = models.CharField(max_length=150, unique=True)
    short_code = models.CharField(max_length=15, unique=True)       # "UAP"
    latitude = models.FloatField(help_text="Campus latitude, e.g. 23.7461")
    longitude = models.FloatField(help_text="Campus longitude, e.g. 90.3742")

    class Meta:
        verbose_name_plural = "universities"
        ordering = ["short_code"]

    def allows_email(self, email):
        """True if this address ends with one of the university's domains."""
        email = (email or "").lower().strip()

        for entry in self.email_domains.all():
            if email.endswith("@" + entry.domain):
                return True
        return False

    @property
    def domain_list(self):
        """'uap-bd.edu or students.uap-bd.edu' — used in error messages."""
        domains = [entry.domain for entry in self.email_domains.all()]

        if not domains:
            return ""
        if len(domains) == 1:
            return domains[0]
        return ", ".join(domains[:-1]) + " or " + domains[-1]

    def __str__(self):
        return self.short_code


class UniversityEmailDomain(models.Model):
    """One allowed email domain. A university can have several.

    North South uses both northsouth.edu and northsouth.ac.bd, and many
    universities give students a different domain from staff. A single
    field on University would reject half of them.
    """

    university = models.ForeignKey(
        University, on_delete=models.CASCADE, related_name="email_domains",
    )
    domain = models.CharField(
        max_length=100,
        unique=True,
        help_text="No @ and no spaces — e.g. uap-bd.edu",
    )
    note = models.CharField(max_length=60, blank=True)

    class Meta:
        ordering = ["university__short_code", "domain"]

    def save(self, *args, **kwargs):
        # Tidy it on the way in, so "@UAP-BD.EDU " still matches later.
        self.domain = self.domain.strip().lstrip("@").lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"@{self.domain}"


class User(AbstractUser):
    """Our user, replacing Django's default.

    AbstractUser already gives username, email, password, is_active and
    is_staff. We only add what UniFlatMate needs.
    """

    class Gender(models.TextChoices):
        MALE = "M", "Male"
        FEMALE = "F", "Female"

    gender = models.CharField(max_length=1, choices=Gender.choices)
    is_verified = models.BooleanField(
        default=False,
        help_text="True once the link sent to the university email is clicked.",
    )

    def __str__(self):
        return self.username


class Student(User):
    """A student profile.

    Student inherits from User. Django stores that as a separate table
    whose primary key is also a foreign key to the user table — this is
    called multi-table inheritance.
    """

    class Department(models.TextChoices):
        CSE = "CSE", "Computer Science & Engineering"
        SWE = "SWE", "Software Engineering"
        EEE = "EEE", "Electrical & Electronic Engineering"
        CE = "CE", "Civil Engineering"
        ME = "ME", "Mechanical Engineering"
        IPE = "IPE", "Industrial & Production Engineering"
        ARCH = "ARCH", "Architecture"
        TE = "TE", "Textile Engineering"
        BBA = "BBA", "Business Administration"
        ECO = "ECO", "Economics"
        ENG = "ENG", "English"
        LAW = "LAW", "Law"
        PHARM = "PHARM", "Pharmacy"
        BGE = "BGE", "Biotechnology & Genetic Engineering"
        MICRO = "MICRO", "Microbiology"
        PH = "PH", "Public Health"
        MCJ = "MCJ", "Media & Journalism"
        MATH = "MATH", "Mathematics"
        PHY = "PHY", "Physics"
        OTHER = "OTHER", "Other"

    class Season(models.TextChoices):
        SPRING = "SP", "Spring"
        SUMMER = "SU", "Summer"
        FALL = "FA", "Fall"

    university = models.ForeignKey(
        University, on_delete=models.PROTECT, related_name="students",
    )

    # Department and batch are safe to show publicly. roll_number is not.
    department = models.CharField(max_length=10, choices=Department.choices)

    # Two columns, not the text "Spring 2024", so the year can be sorted.
    batch_season = models.CharField(max_length=2, choices=Season.choices)
    batch_year = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(2000), MaxValueValidator(2100)],
        help_text="The year you started, e.g. 2024",
    )

    roll_number = models.CharField(
        max_length=30,
        help_text="PRIVATE. Never show on a public profile — use .public_label.",
    )
    budget = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Monthly budget in BDT. Used by the compatibility score.",
    )
    contact_number = models.CharField(
        max_length=15, blank=True,
        help_text="PRIVATE. Shown only after a roommate request is accepted.",
    )

    # the inputs to the compatibility score
    smokes = models.BooleanField(default=False)
    sleeps_early = models.BooleanField(default=True)
    study_at_home = models.BooleanField(default=True)

    # "mess.Mess" as a string, not an import, so accounts and mess do not
    # import each other.
    mess = models.ForeignKey(
        "mess.Mess",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="members",
    )

    @property
    def batch(self):
        """'Spring 2024', rebuilt from the two stored columns."""
        return f"{self.get_batch_season_display()} {self.batch_year}"

    @property
    def public_label(self):
        """Safe to show others: identity without traceability."""
        return f"{self.department}, {self.university.short_code} — {self.batch}"

    def connections(self):
        """Accepted roommate requests, whether I sent or received them.

        Q(...) | Q(...) is Django's way of writing OR, and the keyword
        argument after it is ANDed on. So: (I sent OR I received) AND
        accepted.
        """
        sent_or_received = Q(sender=self) | Q(receiver=self)

        return (RoommateRequest.objects
                .filter(sent_or_received,
                        status=RoommateRequest.Status.ACCEPTED)
                .select_related("sender__university", "receiver__university"))

    def __str__(self):
        return f"{self.username} ({self.university.short_code})"


class Owner(User):
    """A house or mess owner. Posts listings; handles no money here."""

    owner_rating = models.DecimalField(
        max_digits=3, decimal_places=2, default=0.00,
    )
    contact_number = models.CharField(
        max_length=15, blank=True,
        help_text="Shown to a student only after a seat request is accepted.",
    )

    def refresh_rating(self):
        """Work out the average rating again and save it.

        Storing the average means the search page can show it without an
        extra query per row. Review.save() and Review.delete() call this.
        """
        from django.db.models import Avg

        average = self.received_reviews.aggregate(a=Avg("rating"))["a"]

        if average is None:
            self.owner_rating = 0
        else:
            self.owner_rating = round(average, 2)

        self.save(update_fields=["owner_rating"])

    @property
    def review_count(self):
        return self.received_reviews.count()

    def __str__(self):
        return f"{self.username} (Owner)"


class RoommateRequest(models.Model):
    """One student asks another to be roommates. The other one decides.

    Not the same as listings.SeatRequest, which an owner decides.
    """

    class Status(models.TextChoices):
        PENDING = "P", "Pending"
        ACCEPTED = "A", "Accepted"
        DECLINED = "D", "Declined"

    sender = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="sent_requests",
    )
    receiver = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="received_requests",
    )
    status = models.CharField(
        max_length=1, choices=Status.choices, default=Status.PENDING,
    )
    message = models.TextField(blank=True, max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # One request per pair, enforced by the database.
            models.UniqueConstraint(
                fields=["sender", "receiver"], name="one_request_per_pair",
            ),
        ]
        ordering = ["-created_at"]

    def involves(self, student):
        """True if this student is one of the two people."""
        if student is None:
            return False
        return student.pk in (self.sender_id, self.receiver_id)

    def other_party(self, student):
        """The person on the other end, or None."""
        if student is None:
            return None
        if student.pk == self.sender_id:
            return self.receiver
        if student.pk == self.receiver_id:
            return self.sender
        return None

    def contact_visible_to(self, student):
        """May this student see the other one's email and phone?

        Two conditions: the request was accepted, and the viewer is one of
        the two. Nothing is stored as a flag, so declining later hides the
        details again straight away.
        """
        if self.status != self.Status.ACCEPTED:
            return False
        return self.involves(student)

    def __str__(self):
        return f"{self.sender} -> {self.receiver} ({self.get_status_display()})"
