"""The review form."""

from django import forms

from .models import Review


class ReviewForm(forms.ModelForm):
    """Rate an owner out of five.

    The anonymous box is on by default and kept prominent, because the
    student may still be living in this owner's house.
    """

    RATING_CHOICES = [
        (5, "5 — excellent"),
        (4, "4 — good"),
        (3, "3 — okay"),
        (2, "2 — poor"),
        (1, "1 — avoid"),
    ]

    # coerce=int because an HTML form sends "5", not 5.
    rating = forms.TypedChoiceField(
        choices=RATING_CHOICES, coerce=int, label="Rating",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = Review
        fields = ("rating", "comment", "is_anonymous")
        labels = {
            "comment": "What should other students know?",
            "is_anonymous": "Post anonymously",
        }
        help_texts = {
            "is_anonymous": "Recommended. Your name is never shown and the "
                            "owner cannot tell who wrote it.",
        }
        widgets = {
            "comment": forms.Textarea(attrs={
                "rows": 4, "class": "form-control",
                "placeholder": "Water supply, how repairs were handled, "
                               "whether the rent matched what was agreed…",
            }),
            "is_anonymous": forms.CheckboxInput(
                attrs={"class": "form-check-input"}),
        }
