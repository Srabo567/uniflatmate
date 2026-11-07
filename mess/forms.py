"""Meal entry and expense entry."""

from django import forms

from .models import DailyMeal, MessExpense


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


class DailyMealForm(forms.ModelForm):
    """One row: this student ate this many meals on this day.

    The unique constraint already stops a second row for the same day, but
    that shows as a 500 page. clean() catches it first and says it in
    words.
    """

    class Meta:
        model = DailyMeal
        fields = ("student", "meal_date", "meal_count")
        widgets = {"meal_date": forms.DateInput(attrs={"type": "date"})}
        labels = {
            "student": "Member",
            "meal_date": "Date",
            "meal_count": "Meals (0.5 allowed)",
        }

    def __init__(self, *args, mess=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.mess = mess

        # Only this mess's members. Without it the dropdown would list
        # every student on the platform.
        if mess is not None:
            self.fields["student"].queryset = mess.members.all()

        add_bootstrap_classes(self)

    def clean(self):
        cleaned = super().clean()
        student = cleaned.get("student")
        meal_date = cleaned.get("meal_date")

        if self.mess is None or student is None or meal_date is None:
            return cleaned

        clash = DailyMeal.objects.filter(
            mess=self.mess, student=student, meal_date=meal_date)

        # When editing, the row being edited is not a clash with itself.
        if self.instance.pk:
            clash = clash.exclude(pk=self.instance.pk)

        if clash.exists():
            raise forms.ValidationError(
                f"{student.username} already has an entry for {meal_date}. "
                f"Edit that row instead of adding a second."
            )

        return cleaned


class MessExpenseForm(forms.ModelForm):
    """Money one member spent on behalf of the group."""

    class Meta:
        model = MessExpense
        fields = ("payer", "amount", "expense_type", "note", "spent_on")
        widgets = {"spent_on": forms.DateInput(attrs={"type": "date"})}
        labels = {
            "payer": "Who paid",
            "amount": "Amount (BDT)",
            "expense_type": "Type",
            "note": "What for",
            "spent_on": "Date",
        }

    def __init__(self, *args, mess=None, **kwargs):
        super().__init__(*args, **kwargs)

        if mess is not None:
            self.fields["payer"].queryset = mess.members.all()

        add_bootstrap_classes(self)

    def clean_amount(self):
        amount = self.cleaned_data["amount"]

        if amount <= 0:
            raise forms.ValidationError("Amount must be more than zero.")

        return amount
