"""
accounts/models.py  —  WORKED EXAMPLE

Read this file first. Every other models.py in the project is this same
pattern with different fields, so once you understand this one the rest is
mechanical.

Covers the class diagram's University, User, Student, Owner and
RoommateRequest.
"""

from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q


class University(models.Model):
    """
    One row per campus.

    UniFlatMate is open to students of any university, so this is a real
    table rather than a text field on Student. The coordinates are what make
    "seats within 3 km of my campus" possible — see listings/services.py.

    Rows are loaded by `python manage.py seed_universities`, not typed into
    the admin by hand — see accounts/management/commands/.
    """

    name = models.CharField(max_length=150, unique=True)
    short_code = models.CharField(max_length=15, unique=True)       # "UAP"
    latitude = models.FloatField(help_text="Campus latitude, e.g. 23.7461")
    longitude = models.FloatField(help_text="Campus longitude, e.g. 90.3742")

    class Meta:
        verbose_name_plural = "universities"
        ordering = ["short_code"]

    def allows_email(self, email):
        """
        True if this address is on one of the university's own domains.

        THE VERIFICATION RULE lives here, on the model, so that forms, the
        admin and any future API all apply the same test. A form should ask
        the model a question, not re-implement the answer.
        """
        email = (email or "").lower().strip()
        return any(
            email.endswith("@" + d.domain)
            for d in self.email_domains.all()
        )

    @property
    def domain_list(self):
        """'uap-bd.edu or students.uap-bd.edu' — for error messages."""
        domains = [d.domain for d in self.email_domains.all()]
        if len(domains) <= 1:
            return domains[0] if domains else ""
        return ", ".join(domains[:-1]) + " or " + domains[-1]

    def __str__(self):
        return self.short_code


class UniversityEmailDomain(models.Model):
    """
    One allowed email domain. A university may have several.

    WHY THIS IS ITS OWN TABLE: the first design put a single email_domain
    field on University. That breaks on real data — North South publishes
    both northsouth.edu and northsouth.ac.bd, and several universities give
    students a different domain from staff (students.x.edu.bd vs x.edu.bd).
    With one field, half of a university's students get rejected at sign-up.

    This is a plain one-to-many: one University, many domains. It is the
    same shape as University -> Student, so nothing new to learn.
    """

    university = models.ForeignKey(
        University, on_delete=models.CASCADE, related_name="email_domains",
    )
    domain = models.CharField(
        max_length=100,
        unique=True,                 # no two universities may claim one domain
        help_text="No @ and no spaces — e.g. uap-bd.edu",
    )
    note = models.CharField(
        max_length=60, blank=True,
        help_text="Optional, e.g. 'student accounts' or 'old domain'.",
    )

    class Meta:
        ordering = ["university__short_code", "domain"]

    def save(self, *args, **kwargs):
        # Normalise on the way in, so a stray "@UAP-BD.EDU " can never
        # silently fail to match a lowercase address later.
        self.domain = self.domain.strip().lstrip("@").lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"@{self.domain}"


class User(AbstractUser):
    """
    Our custom user, replacing Django's default.

    AbstractUser already gives us, free:
        username (unique — the [UNIQUE] on the class diagram),
        email, first_name, last_name,
        password (hashed automatically — never store a raw password),
        is_active, is_staff, date_joined.

    So we only add what UniFlatMate needs on top.
    """

    class Gender(models.TextChoices):
        # TextChoices gives a dropdown in forms and the admin, and stops
        # 'male', 'MALE', 'M ' and 'm' all landing in the same column.
        MALE = "M", "Male"
        FEMALE = "F", "Female"

    gender = models.CharField(max_length=1, choices=Gender.choices)
    is_verified = models.BooleanField(
        default=False,
        help_text="True once the student clicked the link sent to their "
                  "university email. THIS is what verification means — a "
                  "roll number proves nothing, anyone can type one.",
    )

    def __str__(self):
        # Whatever this returns is what shows in the admin and in dropdowns.
        # Always define it; the default is useless.
        return self.username


class Student(User):
    """
    A student profile.

    NOTE ON THE DIAGRAM: the class diagram shows Student inheriting from
    User, with its own student_id [PK] and a user_id [FK to User]. That is
    exactly what Django does here — it is called multi-table inheritance.
    Django creates an accounts_student table whose primary key is also a
    foreign key to accounts_user. Diagram and code agree.

    If Sir asks: "Student inherits from User; in the database Django stores
    it as a separate table linked one-to-one by the primary key."
    """

    class Department(models.TextChoices):
        """
        A fixed list, not free text.

        WHY: as a CharField, four students typing "CSE", "cse", "Cse" and
        "Computer Science" produce four different departments. The ?dept=
        filter on the match page then silently misses people, and profiles
        look inconsistent. The stored value is the short code, so the filter
        keeps working; the long name is only what the dropdown shows.
        """
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

    # --- academic identity ---
    # department and batch are safe to show publicly; roll_number is NOT.
    # Name + department + roll makes a student findable in the real world,
    # which is the exact risk the female-safety objective exists to prevent.
    department = models.CharField(max_length=10, choices=Department.choices)

    # Batch is stored as two columns, not the string "Spring 2024". Storing
    # the year as a number means you can sort and filter by it ("everyone
    # from 2024 or later"), which you cannot do with text.
    batch_season = models.CharField(max_length=2, choices=Season.choices)
    batch_year = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(2000), MaxValueValidator(2100)],
        help_text="The year you started, e.g. 2024",
    )

    roll_number = models.CharField(
        max_length=30,
        help_text="PRIVATE. Never render this on a public profile — show "
                  "department and batch instead. Use .public_label.",
    )

    budget = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Monthly budget in BDT. Used by the compatibility score.",
    )

    contact_number = models.CharField(
        max_length=15, blank=True,
        help_text="PRIVATE. Shown only to students whose roommate request "
                  "you have accepted — never on a profile or a match card. "
                  "Optional: email alone is enough to connect.",
    )

    # --- lifestyle attributes: the inputs to the compatibility score ---
    smokes = models.BooleanField(default=False)
    sleeps_early = models.BooleanField(default=True)
    study_at_home = models.BooleanField(
        default=True, help_text="True if they mainly study in the room.",
    )

    # The mess this student currently eats with, if any.
    #
    # The string "mess.Mess" rather than importing the class is what avoids
    # a circular import: accounts does not import mess, and mess does not
    # import accounts. Django resolves the string at startup.
    # mess app এখনো লেখা হয়নি, তাই এই field টা আপাতত বন্ধ।
    # তাজকিয়ার mess merge হওয়ার পর এই চার লাইন খুলে দিয়ে
    # makemigrations + migrate চালালেই হবে — আলাদা একটা commit।
    # mess = models.ForeignKey(
    #     "mess.Mess", on_delete=models.SET_NULL,
    #     null=True, blank=True, related_name="members",
    # )

    @property
    def batch(self):
        """'Spring 2024' — rebuilt for display from the two stored columns."""
        return f"{self.get_batch_season_display()} {self.batch_year}"

    @property
    def public_label(self):
        """Safe to show other students: identity without traceability."""
        return f"{self.department}, {self.university.short_code} — {self.batch}"

    def connections(self):
        """
        Accepted roommate connections, in BOTH directions.

        A connection is not a separate table — it is simply a
        RoommateRequest that reached ACCEPTED. The person may have been the
        sender or the receiver, so the query has to look at both columns;
        that is what the Q objects are for. Q(...) | Q(...) is Django's way
        of writing SQL's OR, and the keyword argument after it is ANDed on.

        So this reads: (I sent it OR I received it) AND it was accepted.
        """
        return (RoommateRequest.objects
                .filter(Q(sender=self) | Q(receiver=self),
                        status=RoommateRequest.Status.ACCEPTED)
                .select_related("sender__university", "receiver__university"))

    def __str__(self):
        return f"{self.username} ({self.university.short_code})"


class Owner(User):
    """A house or mess owner. Posts listings; handles no money here."""

    owner_rating = models.DecimalField(
        max_digits=3, decimal_places=2, default=0.00,
        help_text="Average of all reviews; recalculated when one is added.",
    )
    contact_number = models.CharField(
        max_length=15, blank=True,
        help_text="Revealed to a student only after a SeatRequest is "
                  "accepted — never shown on a public listing.",
    )

    def refresh_rating(self):
        """
        Recalculate owner_rating from the reviews, and save it.

        WHY STORE IT AT ALL, instead of averaging on every page view?
        Because the search page shows a rating per listing. Averaging live
        would be one extra query per row — the N+1 problem again. So the
        average is computed once, when a review changes, and read for free
        afterwards. The cost is that this method must be called whenever a
        review is added, edited or deleted; Review.save() and
        Review.delete() do exactly that.
        """
        from django.db.models import Avg

        average = self.received_reviews.aggregate(a=Avg("rating"))["a"]
        self.owner_rating = round(average, 2) if average is not None else 0
        self.save(update_fields=["owner_rating"])

    @property
    def review_count(self):
        return self.received_reviews.count()

    def __str__(self):
        return f"{self.username} (Owner)"


class RoommateRequest(models.Model):
    """
    Student -> Student.  THE OTHER STUDENT DECIDES.

    Do not confuse this with listings.SeatRequest, which is Student ->
    Listing and is decided by the OWNER. Two different requests, two
    different deciders — that is why they are two tables, not one.
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
        # One student cannot spam another with twenty requests. This is a
        # real database constraint, not a check in Python — worth saying in
        # the viva.
        constraints = [
            models.UniqueConstraint(
                fields=["sender", "receiver"], name="one_request_per_pair",
            ),
        ]
        ordering = ["-created_at"]

    # -----------------------------------------------------------------
    #  WHAT ACCEPTING ACTUALLY DOES
    #
    #  Before this, accepting a request changed a letter in a column and
    #  nothing else — two students were "matched" with no way to reach
    #  each other. Accepting now unlocks contact details.
    #
    #  The rule is written here, on the model, NOT in a template. A
    #  template that decides who sees a phone number is a privacy bug
    #  waiting to happen: the next person to add a page forgets the check
    #  and the number leaks. One method, used everywhere.
    # -----------------------------------------------------------------

    def involves(self, student):
        """True if this student is one of the two parties."""
        return student is not None and student.pk in (self.sender_id,
                                                      self.receiver_id)

    def other_party(self, student):
        """The person on the other end, or None if they are not involved."""
        if student is None:
            return None
        if student.pk == self.sender_id:
            return self.receiver
        if student.pk == self.receiver_id:
            return self.sender
        return None

    def contact_visible_to(self, student):
        """
        May this student see the other one's email and phone?

        TWO conditions, both required:
          1. the request was ACCEPTED — pending and declined reveal nothing
          2. the viewer is one of the two parties — nobody else, ever,
             including staff browsing the site as a normal user

        Declining later re-hides the details, because this is evaluated
        fresh on every request rather than stored as a flag.
        """
        return self.status == self.Status.ACCEPTED and self.involves(student)

    def __str__(self):
        return f"{self.sender} -> {self.receiver} ({self.get_status_display()})"
