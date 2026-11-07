"""The meal-rate arithmetic.

    Meal Rate = total shared expense / total meals recorded

Every query below is scoped with mess=mess. Removing that would add up
every mess on the platform — see the note in models.py.
"""

from decimal import Decimal

from django.db.models import Sum


def total_expense_of(mess):
    """All money spent for this mess, as a Decimal."""
    from .models import MessExpense

    result = MessExpense.objects.filter(mess=mess).aggregate(total=Sum("amount"))
    return result["total"] or Decimal("0.00")


def total_meals_of(mess):
    """All meals eaten in this mess, as a Decimal."""
    from .models import DailyMeal

    result = DailyMeal.objects.filter(mess=mess).aggregate(total=Sum("meal_count"))
    return result["total"] or Decimal("0.00")


def calculate_meal_rate(mess):
    """What one meal costs in this mess.

    Returns 0 when nobody has eaten yet. Without that check the page would
    crash with a divide-by-zero on the first day of the month — which is
    exactly when someone opens it.
    """
    total_expense = total_expense_of(mess)
    total_meals = total_meals_of(mess)

    if total_meals == 0:
        return Decimal("0.00")

    return (total_expense / total_meals).quantize(Decimal("0.01"))


def member_summary(mess):
    """Per-student breakdown for the dashboard.

    A positive balance means the group owes them; negative means they owe
    the group. UniFlatMate only reports this — settling up happens between
    the students themselves.
    """
    from .models import DailyMeal, MessExpense

    rate = calculate_meal_rate(mess)
    rows = []

    for student in mess.members.all():
        meal_total = DailyMeal.objects.filter(
            mess=mess, student=student).aggregate(total=Sum("meal_count"))
        meals = meal_total["total"] or Decimal("0.00")

        paid_total = MessExpense.objects.filter(
            mess=mess, payer=student).aggregate(total=Sum("amount"))
        paid = paid_total["total"] or Decimal("0.00")

        consumed = (meals * rate).quantize(Decimal("0.01"))

        rows.append({
            "student": student,
            "meals": meals,
            "paid": paid,
            "consumed": consumed,
            "balance": paid - consumed,
        })

    return {"meal_rate": rate, "members": rows}
