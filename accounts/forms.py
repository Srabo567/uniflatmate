"""Sign-up and profile forms.

clean_email() is where the "verified student network" rule becomes code:
the email must be on the chosen university's own domain.
"""

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from .models import Owner, Student, University


def add_bootstrap_classes(form):
    """Give every widget the right Bootstrap class."""
    for field in form.fields.values():
        widget = field.widget

        if isinstance(widget, forms.CheckboxInput):
            widget.attrs.setdefault("class", "form-check-input")
        elif isinstance(widget, forms.Select):
            widget.attrs.setdefault("class", "form-select")
        else:
            widget.attrs.setdefault("class", "form-control")


def email_already_used(email):
    """True if any account — student or owner — already has this address."""
    return get_user_model().objects.filter(email__iexact=email).exists()


class StudentSignUpForm(UserCreationForm):
    """Creates a Student, and the User row underneath it.

    UserCreationForm already handles username, both password boxes and
    password strength. We add the Student fields.
    """

    email = forms.EmailField(
        required=True,
        help_text="Your university email — a confirmation link is sent here.",
    )

    class Meta:
        model = Student
        fields = (
            "username", "email", "gender",
            "university", "department", "batch_season", "batch_year",
            "roll_number",
            "contact_number",
            "budget", "smokes", "sleeps_early", "study_at_home",
        )
        labels = {
            "budget": "Monthly budget (BDT)",
            "batch_season": "Batch season",
            "batch_year": "Batch year",
            "roll_number": "Roll / student ID",
            "contact_number": "Phone number (optional)",
            "smokes": "I smoke",
            "sleeps_early": "I sleep early",
            "study_at_home": "I mostly study in my room",
        }
        help_texts = {
            "roll_number": "Kept private — never shown on your profile.",
            "contact_number": "Shown only to someone whose roommate request "
                              "you accept. Leave blank to connect by email.",
            "budget": "Used by the compatibility score.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        add_bootstrap_classes(self)

        # prefetch so one query covers every university's domains
        self.fields["university"].queryset = (
            University.objects.prefetch_related("email_domains")
        )
        self.fields["university"].empty_label = "Select your university"

    def clean_email(self):
        """The email must be on the chosen university's domain.

        A roll number proves nothing — anyone can type one. The test itself
        lives on the model, so the admin applies the same rule.
        """
        email = self.cleaned_data["email"].lower().strip()

        # self.data, not cleaned_data: university may not be cleaned yet.
        university_id = self.data.get("university")
        university = None
        if university_id:
            university = University.objects.filter(pk=university_id).first()

        if university is not None and not university.allows_email(email):
            if university.domain_list:
                raise forms.ValidationError(
                    f"Use your {university.short_code} email address — "
                    f"it must end with @{university.domain_list}"
                )
            raise forms.ValidationError(
                f"{university.short_code} has no verified email domain on "
                f"file yet, so sign-up is closed for it. Ask an admin to "
                f"add one."
            )

        if email_already_used(email):
            raise forms.ValidationError("An account with this email already exists.")

        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]

        # Inactive until the emailed link is clicked.
        user.is_active = False
        user.is_verified = False

        if commit:
            user.save()
        return user


class OwnerSignUpForm(UserCreationForm):
    """Creates an Owner.

    Owners are not students, so there is no university email to check and
    no lifestyle questions. An admin verifies them instead.
    """

    email = forms.EmailField(required=True)

    class Meta:
        model = Owner
        fields = ("username", "email", "gender", "contact_number")
        labels = {"contact_number": "Phone number"}
        help_texts = {
            "contact_number": "Shown to a student only after you accept "
                              "their seat request — never on a public listing.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        add_bootstrap_classes(self)

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()

        if email_already_used(email):
            raise forms.ValidationError("An account with this email already exists.")

        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.is_active = False      # the emailed link activates it
        user.is_verified = False    # an admin confirms owners separately

        if commit:
            user.save()
        return user


class StudentProfileForm(forms.ModelForm):
    """The parts of a profile a student may change.

    Username, email, university and roll_number are left out — those are
    what the account was verified against.
    """

    class Meta:
        model = Student
        fields = ("department", "batch_season", "batch_year",
                  "contact_number", "budget",
                  "smokes", "sleeps_early", "study_at_home")
        labels = {
            "budget": "Monthly budget (BDT)",
            "batch_season": "Batch season",
            "batch_year": "Batch year",
            "contact_number": "Phone number (optional)",
            "smokes": "I smoke",
            "sleeps_early": "I sleep early",
            "study_at_home": "I mostly study in my room",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        add_bootstrap_classes(self)
