"""Forms for posting a room, asking for a seat, and searching."""

from django import forms
from django.forms import inlineformset_factory

from locations.models import Area

from .models import Listing, ListingPhoto, SeatRequest


def add_bootstrap_classes(form):
    """Give every widget the right Bootstrap class."""
    for field in form.fields.values():
        widget = field.widget

        if isinstance(widget, forms.CheckboxInput):
            widget.attrs.setdefault("class", "form-check-input")
        elif isinstance(widget, forms.CheckboxSelectMultiple):
            pass
        elif isinstance(widget, forms.HiddenInput):
            pass
        elif isinstance(widget, forms.Select):
            widget.attrs.setdefault("class", "form-select")
        else:
            widget.attrs.setdefault("class", "form-control")


class ListingForm(forms.ModelForm):
    """Post or edit a room.

    Latitude and longitude are hidden. The owner drags a pin on the map and
    the template's JavaScript fills them in.
    """

    class Meta:
        model = Listing
        fields = (
            "title", "description",
            "area", "latitude", "longitude",
            "rent", "floor", "washroom", "furnishing", "cooking",
            "seats_total", "seats_available", "available_from",
            "amenities", "is_female_only", "is_available",
        )
        widgets = {
            "latitude": forms.HiddenInput(),
            "longitude": forms.HiddenInput(),
            "description": forms.Textarea(attrs={"rows": 4}),
            "available_from": forms.DateInput(attrs={"type": "date"}),
            "amenities": forms.CheckboxSelectMultiple(),
        }
        labels = {
            "rent": "Monthly rent (BDT)",
            "floor": "Floor number",
            "washroom": "Washroom",
            "cooking": "Cooking facility",
            "seats_total": "Total seats",
            "seats_available": "Seats still free",
            "is_female_only": "Female students only",
            "is_available": "Listing is live",
        }
        help_texts = {
            "rent": "Shown as information. Paid directly to you.",
            "floor": "0 for ground floor.",
            "is_female_only": "Only female students will see this listing.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["area"].queryset = Area.objects.all()
        self.fields["area"].empty_label = "Select the area"
        add_bootstrap_classes(self)

    def clean(self):
        """Checks that need two fields at once."""
        cleaned = super().clean()
        total = cleaned.get("seats_total")
        free = cleaned.get("seats_available")

        if total is not None and free is not None and free > total:
            self.add_error(
                "seats_available",
                f"You cannot have {free} seats free out of {total}.",
            )

        if total == 0:
            self.add_error("seats_total", "A listing needs at least one seat.")

        return cleaned


# Several photo forms on one page, all tied to one listing.
ListingPhotoFormSet = inlineformset_factory(
    Listing,
    ListingPhoto,
    fields=("image", "caption", "is_cover"),
    extra=3,
    max_num=8,
    can_delete=True,
    widgets={
        "caption": forms.TextInput(attrs={
            "class": "form-control form-control-sm",
            "placeholder": "Kitchen, washroom, balcony…",
        }),
        "image": forms.ClearableFileInput(attrs={
            "class": "form-control form-control-sm",
            "accept": "image/*",
        }),
    },
)


class SeatRequestForm(forms.ModelForm):
    """One optional line a student sends with a seat request."""

    class Meta:
        model = SeatRequest
        fields = ("message",)
        labels = {"message": "Message to the owner (optional)"}
        widgets = {
            "message": forms.Textarea(attrs={
                "rows": 3, "class": "form-control",
                "placeholder": "When could I come and see the room?",
            }),
        }


class ListingSearchForm(forms.Form):
    """The student search. A plain Form — it filters, it saves nothing."""

    radius_km = forms.ChoiceField(
        choices=[(1, "Within 1 km"), (2, "Within 2 km"), (3, "Within 3 km"),
                 (4, "Within 4 km"), (5, "Within 5 km")],
        initial=3,
        label="Distance from campus",
    )
    max_rent = forms.DecimalField(
        required=False, label="Maximum rent (BDT)",
        widget=forms.NumberInput(attrs={"placeholder": "Any"}),
    )
    washroom = forms.ChoiceField(required=False, label="Washroom", choices=[])
    female_only = forms.BooleanField(
        required=False, label="Female-only listings only",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["washroom"].choices = (
            [("", "Any")] + list(Listing.Washroom.choices)
        )

        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select form-select-sm")
            else:
                widget.attrs.setdefault("class", "form-control form-control-sm")
