"""The shared-meal dashboard.

The view fetches, services.py calculates, the template shows.

A khata is private to its own mess. Every view below checks membership
first, and the check lives on the model (Mess.can_view), not in a
template.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import Student

from .forms import DailyMealForm, MessExpenseForm
from .models import DailyMeal, Mess, MessExpense
from .services import member_summary


def get_student(request):
    """The Student account for this user, or None."""
    return Student.objects.filter(pk=request.user.pk).first()


def mess_or_404(pk, student):
    """The mess, but only if this student is allowed to see it.

    404 rather than 403, so changing the number in the address bar tells a
    stranger nothing about which messes exist.
    """
    mess = get_object_or_404(Mess, pk=pk)

    if not mess.can_view(student):
        raise Http404("No mess matches the given query.")

    return mess


@login_required
def my_mess(request):
    """Send the student to their own mess, or explain they have none."""
    student = get_student(request)
    if student is None:
        return render(request, "matching/not_a_student.html")

    mess = student.mess
    if mess is None:
        return render(request, "mess/no_mess.html", {"student": student})

    return redirect("mess:dashboard", pk=mess.pk)


@login_required
def dashboard(request, pk):
    """The khata: meal rate, every member's balance, recent entries."""
    student = get_student(request)

    mess = get_object_or_404(
        Mess.objects.select_related("listing__area", "manager"), pk=pk)
    if not mess.can_view(student):
        raise Http404("No mess matches the given query.")

    summary = member_summary(mess)
    rows = summary["members"]

    total_expense = 0
    total_meals = 0
    for row in rows:
        total_expense += row["paid"]
        total_meals += row["meals"]

    recent_meals = (DailyMeal.objects
                    .filter(mess=mess)
                    .select_related("student")[:10])
    recent_expenses = (MessExpense.objects
                       .filter(mess=mess)
                       .select_related("payer")[:10])

    return render(request, "mess/dashboard.html", {
        "mess": mess,
        "student": student,
        "is_manager": mess.is_manager(student),
        "meal_rate": summary["meal_rate"],
        "rows": rows,
        "total_expense": total_expense,
        "total_meals": total_meals,
        "recent_meals": recent_meals,
        "recent_expenses": recent_expenses,
    })


@login_required
def add_meal(request, pk):
    """Record meals for a day.

    Any member may add their own row. The manager may add or correct a row
    for anybody — the way a real mess works.
    """
    student = get_student(request)
    mess = mess_or_404(pk, student)

    if request.method == "POST":
        form = DailyMealForm(request.POST, mess=mess)

        if form.is_valid():
            entry_for = form.cleaned_data["student"]

            # Checked here, not in the template — the browser can send
            # anything, so the server has to decide.
            if not mess.is_manager(student) and entry_for.pk != student.pk:
                messages.error(
                    request,
                    "Only the manager can record meals for someone else.")
                return redirect("mess:dashboard", pk=mess.pk)

            meal = form.save(commit=False)
            meal.mess = mess
            meal.added_by = student
            meal.save()

            messages.success(request, "Meal entry saved.")
            return redirect("mess:dashboard", pk=mess.pk)
    else:
        form = DailyMealForm(
            mess=mess,
            initial={"student": student, "meal_date": timezone.localdate()},
        )

    return render(request, "mess/entry_form.html", {
        "form": form, "mess": mess, "kind": "meal",
    })


@login_required
def add_expense(request, pk):
    """Record a shared cost — bazaar, gas bill, anything the group paid."""
    student = get_student(request)
    mess = mess_or_404(pk, student)

    if request.method == "POST":
        form = MessExpenseForm(request.POST, mess=mess)

        if form.is_valid():
            expense = form.save(commit=False)
            expense.mess = mess
            expense.added_by = student
            expense.save()

            messages.success(request, "Expense recorded.")
            return redirect("mess:dashboard", pk=mess.pk)
    else:
        form = MessExpenseForm(
            mess=mess,
            initial={"payer": student, "spent_on": timezone.localdate()},
        )

    return render(request, "mess/entry_form.html", {
        "form": form, "mess": mess, "kind": "expense",
    })


@login_required
def members(request, pk):
    """Add and remove members. Manager only.

    Without this page the manager role would exist only in the class
    diagram, and members could be set only from /admin/.
    """
    student = get_student(request)
    mess = get_object_or_404(Mess.objects.select_related("manager"), pk=pk)

    if not mess.is_manager(student):
        messages.error(request, "Only the mess manager can manage members.")
        return redirect("mess:dashboard", pk=mess.pk)

    if request.method == "POST":
        handle_member_action(request, mess)
        return redirect("mess:members", pk=mess.pk)

    # Only students at the same university who are not already in a mess.
    # Pulling someone out of another mess would orphan their records there.
    candidates = (
        Student.objects
        .filter(university=student.university, mess__isnull=True)
        .exclude(pk=student.pk)
        .order_by("username")
    )

    return render(request, "mess/members.html", {
        "mess": mess,
        "student": student,
        "current": mess.members.select_related("university"),
        "candidates": candidates,
    })


def handle_member_action(request, mess):
    """Carry out one add or remove from the members page."""
    action = request.POST.get("action")
    target = Student.objects.filter(pk=request.POST.get("student")).first()

    if target is None:
        messages.error(request, "No such student.")
        return

    if action == "add":
        if target.mess_id is not None:
            messages.error(
                request, f"{target.username} is already in another mess.")
            return

        target.mess = mess
        target.save(update_fields=["mess"])
        messages.success(request, f"{target.username} added.")
        return

    if action == "remove":
        if target.pk == mess.manager_id:
            # That would leave the mess with no manager and nobody able to
            # put one back.
            messages.error(
                request,
                "The manager cannot leave their own mess. Hand the mess "
                "to someone else in /admin/ first.")
            return

        if target.mess_id != mess.pk:
            messages.error(request, "They are not in this mess.")
            return

        target.mess = None
        target.save(update_fields=["mess"])
        messages.success(
            request,
            f"{target.username} removed. Their past meal and expense "
            f"records stay in the khata — removing a person must not "
            f"change what everyone already owes.")


@login_required
def delete_meal(request, pk, meal_id):
    """Remove a wrong meal entry. Manager only, POST only."""
    student = get_student(request)
    mess = get_object_or_404(Mess, pk=pk)

    if not mess.is_manager(student):
        messages.error(request, "Only the mess manager can remove entries.")
        return redirect("mess:dashboard", pk=mess.pk)

    if request.method == "POST":
        DailyMeal.objects.filter(pk=meal_id, mess=mess).delete()
        messages.success(request, "Entry removed.")

    return redirect("mess:dashboard", pk=mess.pk)
