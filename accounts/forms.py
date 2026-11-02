"""
accounts/forms.py  —  WORKED EXAMPLE (a form with real validation)

This is where sign-up happens, and where the "verified student network"
objective from the deck actually becomes code.

The important part is clean_email(). A student picks their university from
a dropdown, and the form then REFUSES any email that is not on that
university's domain. That is what stops a random person signing up as a UAP
student.
"""

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from .models import Owner, Student, University


class StudentSignUpForm(UserCreationForm):
    """
    Creates a Student (which, through multi-table inheritance, also creates
    the underlying User row).

    UserCreationForm already gives us username, password1, password2 and
    password confirmation + strength validation. We add the Student fields.
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
        # Bootstrap styling, applied once here instead of in the template.
        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select")
            else:
                widget.attrs.setdefault("class", "form-control")

        # prefetch so one query covers every university's domains
        self.fields["university"].queryset = (
            University.objects.prefetch_related("email_domains")
        )
        self.fields["university"].empty_label = "Select your university"

    def clean_email(self):
        """
        THE VERIFICATION RULE.

        The email must be on one of the chosen university's domains. A roll
        number proves nothing — anyone can type one. The email domain is the
        thing that actually ties a person to a campus.

        The test itself lives on the model (University.allows_email), so the
        admin and any future API apply exactly the same rule. This form only
        decides what the error message says.
        """
        email = self.cleaned_data["email"].lower().strip()

        # self.data, not cleaned_data: university may not be cleaned yet.
        university_id = self.data.get("university")
        if university_id:
            university = University.objects.filter(pk=university_id).first()
            if university and not university.allows_email(email):
                if university.domain_list:
                    raise forms.ValidationError(
                        f"Use your {university.short_code} email address — "
                        f"it must end with @{university.domain_list}"
                    )
                # No domains configured yet: refuse rather than let anyone in.
                raise forms.ValidationError(
                    f"{university.short_code} has no verified email domain on "
                    f"file yet, so sign-up is closed for it. Ask an admin to "
                    f"add one."
                )

        # Check EVERY user, not just students — an owner may already have
        # claimed this address, and two accounts must never share one.
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")

        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]

        # Inactive until the emailed link is clicked. This is what makes
        # verification mean something — an unverified account cannot log in.
        user.is_active = False
        user.is_verified = False

        if commit:
            user.save()
        return user


class OwnerSignUpForm(UserCreationForm):
    """
    Creates an Owner — someone who posts listings.

    Owners are NOT students, so there is no university email to check
    against and no lifestyle questions. They are verified by an admin
    instead, which is why is_verified starts False.
    """

    email = forms.EmailField(required=True)

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

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
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select")
            else:
                widget.attrs.setdefault("class", "form-control")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.is_active = False      # activated by the emailed link
        user.is_verified = False    # an admin confirms owners separately
        if commit:
            user.save()
        return user


class StudentProfileForm(forms.ModelForm):
    """
    Edit the parts of a profile a student is allowed to change.

    Deliberately excludes username, email, university and roll_number —
    those are what the account was verified against, so letting someone
    edit them would undo the verification.
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
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select")
            else:
                widget.attrs.setdefault("class", "form-control")
