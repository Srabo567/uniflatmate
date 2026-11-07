"""A student reviews an owner after living in one of their places.

Anonymous by default, because the student may still be living in that
owner's house when they write it. Without anonymity nobody is honest, and
the rating stops meaning anything.
"""

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Review(models.Model):
    """One student's review of one owner."""

    author = models.ForeignKey(
        "accounts.Student", on_delete=models.CASCADE,
        related_name="written_reviews",
    )
    owner = models.ForeignKey(
        "accounts.Owner", on_delete=models.CASCADE,
        related_name="received_reviews",
    )

    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="1 to 5.",
    )
    comment = models.TextField(blank=True, max_length=1000)

    is_anonymous = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # One review per student per owner, enforced by the database,
            # so one angry student cannot leave fifty one-star reviews.
            models.UniqueConstraint(
                fields=["author", "owner"],
                name="one_review_per_student_owner",
            ),
        ]

    @property
    def display_name(self):
        """The anonymity rule, in one place.

        Never write {% if not review.is_anonymous %} in a template —
        five templates making that decision is five chances to leak a name.
        """
        if self.is_anonymous:
            return "Anonymous"
        return self.author.username

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.owner.refresh_rating()

    def delete(self, *args, **kwargs):
        owner = self.owner
        super().delete(*args, **kwargs)
        owner.refresh_rating()

    def __str__(self):
        return f"{self.display_name} -> {self.owner.username}: {self.rating}/5"
