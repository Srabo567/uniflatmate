"""
mess/models.py  —  Mess, DailyMeal, MessExpense

The shared-meal module: a digital version of the paper "meal khata" that
every mess in Bangladesh keeps in a notebook.

NO MONEY MOVES THROUGH UNIFLATMATE. This records who ate how many meals and
who paid for the bazaar, then reports the difference. Settling up happens
between the students themselves, offline, exactly as it does now.

#########################################################################
READ THIS — IT IS THE MOST IMPORTANT DESIGN POINT IN THE PROJECT
#########################################################################

The prototype in the original idea document computed the meal rate like
this:

    SELECT SUM(amount) FROM mess_expenses      <-- no WHERE clause
    SELECT SUM(meal_count) FROM daily_meals    <-- no WHERE clause

With no mess_id on those tables, that sums the expenses and meals of EVERY
mess on the whole platform and produces one global meal rate for all of
Bangladesh. It looks perfectly fine while there is only one mess in the
database — which is exactly why this kind of bug survives until the demo.

That is why `mess` is a REQUIRED foreign key on both DailyMeal and
MessExpense, and why every query in mess/services.py is scoped by it.
#########################################################################
"""

from django.db import models


class Mess(models.Model):
    """
    A group of students sharing meals at one address.

    One of the members is the manager. That is not a separate account type
    — just a flag on a normal student, like the admin of a Facebook group.
    """

    listing = models.OneToOneField(
        "listings.Listing", on_delete=models.CASCADE, related_name="mess",
        help_text="OneToOne, not ForeignKey — one listing becomes exactly "
                  "one mess.",
    )
    manager = models.ForeignKey(
        "accounts.Student", on_delete=models.PROTECT,
        related_name="managed_messes",
        help_text="Adds and removes members, and corrects wrong entries. "
                  "PROTECT: you cannot delete the student who runs a mess "
                  "and leave it with nobody in charge.",
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
        return student is not None and student.pk == self.manager_id

    def has_member(self, student):
        """Membership check used by every view in this app."""
        return (student is not None
                and getattr(student, "mess_id", None) == self.pk)

    def can_view(self, student):
        """A mess khata is private to the people in that mess."""
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
        help_text="Who typed it in. May be the manager correcting someone "
                  "else's row — corrections stay visible to everyone, which "
                  "is the whole reason a digital khata beats a notebook.",
    )

    class Meta:
        ordering = ["-meal_date"]
        constraints = [
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
        help_text="PROTECT, not CASCADE — deleting a student must not "
                  "silently erase money they spent. Django refuses the "
                  "delete instead, which is correct for a financial record.",
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
