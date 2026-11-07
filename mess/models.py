"""The shared-meal khata: who ate how much, who paid for the bazaar.

No money moves through UniFlatMate. This records the numbers and reports
the difference; the students settle up between themselves, offline.

IMPORTANT — why `mess` is a required foreign key on DailyMeal and
MessExpense: without it, "SUM(amount)" and "SUM(meal_count)" add up every
mess on the whole platform and produce one meal rate for all of them. With
only one mess in the database that looks perfectly correct, which is why
the bug would survive until the demo. Every query in services.py is scoped
by mess for the same reason.
"""

from django.db import models


class Mess(models.Model):
    """A group of students sharing meals at one address.

    One member is the manager. That is not a separate account type, just a
    link to a normal student — like the admin of a Facebook group.
    """

    listing = models.OneToOneField(
        "listings.Listing", on_delete=models.CASCADE, related_name="mess",
        help_text="OneToOne: one listing becomes exactly one mess.",
    )
    manager = models.ForeignKey(
        "accounts.Student", on_delete=models.PROTECT,
        related_name="managed_messes",
        help_text="PROTECT: a mess must never be left with nobody in charge.",
    )
    mess_name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "messes"
        ordering = ["mess_name"]

    @property
    def member_count(self):
        return self.members.count()

    def is_manager(self, student):
        if student is None:
            return False
        return student.pk == self.manager_id

    def has_member(self, student):
        if student is None:
            return False
        return getattr(student, "mess_id", None) == self.pk

    def can_view(self, student):
        """A khata is private to the people in that mess."""
        return self.has_member(student) or self.is_manager(student)

    def __str__(self):
        return self.mess_name


class DailyMeal(models.Model):
    """How many meals one student ate in this mess on one day."""

    student = models.ForeignKey(
        "accounts.Student", on_delete=models.CASCADE, related_name="meals",
    )
    mess = models.ForeignKey(
        Mess, on_delete=models.CASCADE, related_name="meals",
    )
    meal_date = models.DateField()
    meal_count = models.DecimalField(
        max_digits=4, decimal_places=1, default=0,
        help_text="Decimal, not Integer — half meals are a real thing.",
    )
    added_by = models.ForeignKey(
        "accounts.Student", on_delete=models.PROTECT,
        related_name="meal_entries_added", null=True, blank=True,
        help_text="Who typed it in. May be the manager fixing someone "
                  "else's row.",
    )

    class Meta:
        ordering = ["-meal_date"]
        constraints = [
            # One row per student per day in one mess.
            models.UniqueConstraint(
                fields=["student", "mess", "meal_date"],
                name="one_meal_row_per_day",
            ),
        ]

    def __str__(self):
        return f"{self.student.username} · {self.meal_date} · {self.meal_count}"


class MessExpense(models.Model):
    """One shared cost: bazaar, gas bill, whatever the group paid for."""

    class Kind(models.TextChoices):
        BAZAAR = "B", "Bazaar"
        UTILITY = "U", "Utility"
        OTHER = "O", "Other"

    payer = models.ForeignKey(
        "accounts.Student", on_delete=models.PROTECT, related_name="expenses",
        help_text="PROTECT: deleting a student must not erase money they "
                  "spent, because that would change everyone else's balance.",
    )
    mess = models.ForeignKey(
        Mess, on_delete=models.CASCADE, related_name="expenses",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    expense_type = models.CharField(
        max_length=1, choices=Kind.choices, default=Kind.BAZAAR,
    )
    note = models.CharField(max_length=120, blank=True)
    spent_on = models.DateField()
    added_by = models.ForeignKey(
        "accounts.Student", on_delete=models.PROTECT,
        related_name="entries_added", null=True, blank=True,
    )

    class Meta:
        ordering = ["-spent_on"]

    def __str__(self):
        return f"{self.get_expense_type_display()} · {self.amount} · {self.spent_on}"
