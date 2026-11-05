"""
mess/services.py  —  WORKED EXAMPLE (the meal rate)

The arithmetic behind the formula on the slide:

    Meal Rate = Total Shared Expense / Total Meals Recorded

No money moves through UniFlatMate. This reads a shared record and reports
who contributed more or less than they consumed — a digital version of the
paper "meal khata", not a payment system.

NOTE that every query below is scoped with mess=mess. That is the fix for
the aggregation bug described in models.py. Never remove it.
"""

from decimal import Decimal

from django.db.models import Sum


def calculate_meal_rate(mess):
    """
    Cost of one meal in this mess, as a Decimal.

    Returns 0 when nobody has eaten yet — dividing by zero would crash the
    page on the first day of the month, which is exactly when someone opens
    it.
    """
    from .models import DailyMeal, MessExpense

    total_expense = MessExpense.objects.filter(mess=mess).aggregate(
        total=Sum("amount"))["total"] or Decimal("0.00")
    total_meals = DailyMeal.objects.filter(mess=mess).aggregate(
        total=Sum("meal_count"))["total"] or Decimal("0.00")

    if total_meals == 0:
        return Decimal("0.00")
    return (total_expense / total_meals).quantize(Decimal("0.01"))


def member_summary(mess):
    """
    Per-student breakdown for the mess dashboard.

    For each member: meals eaten, money put in, what their meals cost, and
    the difference. A positive balance means the group owes them; negative
    means they owe the group. UniFlatMate only reports this — settling up
    happens between the students themselves, offline.
    """
    from .models import DailyMeal, MessExpense

    rate = calculate_meal_rate(mess)
    rows = []

    for student in mess.members.all():
        meals = DailyMeal.objects.filter(mess=mess, student=student).aggregate(
            total=Sum("meal_count"))["total"] or Decimal("0.00")
        paid = MessExpense.objects.filter(mess=mess, payer=student).aggregate(
            total=Sum("amount"))["total"] or Decimal("0.00")
        consumed = (meals * rate).quantize(Decimal("0.01"))

        rows.append({
            "student": student, "meals": meals, "paid": paid,
            "consumed": consumed, "balance": paid - consumed,
        })

    return {"meal_rate": rate, "members": rows}
