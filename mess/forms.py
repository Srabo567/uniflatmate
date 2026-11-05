"""mess/forms.py — meal entry and expense entry."""

from django import forms

from .models import DailyMeal, MessExpense


def _style(form):
    for field in form.fields.values():
        widget = field.widget
        if isinstance(widget, forms.CheckboxInput):
            widget.attrs.setdefault("class", "form-check-input")
        elif isinstance(widget, forms.Select):
            widget.attrs.setdefault("class", "form-select")
        else:
            widget.attrs.setdefault("class", "form-control")


class DailyMealForm(forms.ModelForm):
    """
    One row: this student ate this many meals on this day.

    The unique constraint on (student, mess, meal_date) means a second
    entry for the same day is a database error rather than a duplicate, so
    clean() turns that into a readable message instead of a 500 page.
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
        if mess is not None:
            # Only this mess's own members. Without this the dropdown lists
            # every student on the platform.
            self.fields["student"].queryset = mess.members.all()
        _style(self)

    def clean(self):
        cleaned = super().clean()
        student = cleaned.get("student")
        meal_date = cleaned.get("meal_date")

        if self.mess and student and meal_date:
            clash = DailyMeal.objects.filter(
                mess=self.mess, student=student, meal_date=meal_date)
            if self.instance.pk:
                clash = clash.exclude(pk=self.instance.pk)
            if clash.exists():
                raise forms.ValidationError(
                    f"{student.username} already has an entry for "
                    f"{meal_date}. Edit that row instead of adding a second."
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
        _style(self)

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount <= 0:
            raise forms.ValidationError("Amount must be more than zero.")
        return amount
