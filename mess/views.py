"""
mess/views.py  —  the shared-meal dashboard

Same shape as the rest of the project: the view fetches, services.py
computes, the template renders. The meal-rate arithmetic is not here.

PRIVACY: a mess khata is private to its own members. Every view below
checks membership before showing anything, and the check lives on the
model (`Mess.can_view`), not in a template.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import Student

from .forms import DailyMealForm, MessExpenseForm
from .models import DailyMeal, Mess, MessExpense
from .services import calculate_meal_rate, member_summary


def _student(request):
    return Student.objects.filter(pk=request.user.pk).first()


def _members_mess(student):
    """The mess this student belongs to, or None."""
    if student is None:
        return None
    return student.mess


@login_required
def my_mess(request):
    """Send the student to their own mess, or explain that they have none."""
    student = _student(request)
    if student is None:
        return render(request, "matching/not_a_student.html")

    mess = _members_mess(student)
    if mess is None:
        return render(request, "mess/no_mess.html", {"student": student})
    return redirect("mess:dashboard", pk=mess.pk)


@login_required
def dashboard(request, pk):
    """
    The khata: meal rate, every member's balance, recent entries.

    Everything on this page comes from services.member_summary(), which
    scopes every query by mess. See the warning in models.py.
    """
    student = _student(request)
    mess = get_object_or_404(
        Mess.objects.select_related("listing__area", "manager"), pk=pk)

    if not mess.can_view(student):
        raise Http404("No mess matches the given query.")

    summary = member_summary(mess)

    return render(request, "mess/dashboard.html", {
        "mess": mess,
        "student": student,
        "is_manager": mess.is_manager(student),
        "meal_rate": summary["meal_rate"],
        "rows": summary["members"],
        "total_expense": sum(r["paid"] for r in summary["members"]),
        "total_meals": sum(r["meals"] for r in summary["members"]),
        "recent_meals": (DailyMeal.objects.filter(mess=mess)
                         .select_related("student")[:10]),
        "recent_expenses": (MessExpense.objects.filter(mess=mess)
                            .select_related("payer")[:10]),
    })


@login_required
def add_meal(request, pk):
    """
    Record meals for a day.

    Any member may add their own row; the MANAGER may add or correct a row
    for anybody. That mirrors how a real mess works — one person keeps the
    khata, but everyone can write their own line.
    """
    student = _student(request)
    mess = get_object_or_404(Mess, pk=pk)
    if not mess.can_view(student):
        raise Http404("No mess matches the given query.")

    if request.method == "POST":
        form = DailyMealForm(request.POST, mess=mess)
        if form.is_valid():
            # A non-manager may only record their own meals, whatever the
            # form was submitted with. Enforced here, not in the template.
            if not mess.is_manager(student) and \
                    form.cleaned_data["student"].pk != student.pk:
                messages.error(
                    request, "Only the manager can record meals for someone "
                             "else.")
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
    student = _student(request)
    mess = get_object_or_404(Mess, pk=pk)
    if not mess.can_view(student):
        raise Http404("No mess matches the given query.")

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
    """
    Add and remove members. MANAGER ONLY.

    This is what the manager role actually means in the product. Without
    this page the role exists in the class diagram and nowhere else, and
    members can only be set from /admin/ — which no real mess manager is
    ever going to open.

    Candidates are deliberately narrow: students at the same university who
    are not already in a mess. Pulling someone out of another mess would
    orphan their meal records there.
    """
    student = _student(request)
    mess = get_object_or_404(Mess.objects.select_related("manager"), pk=pk)

    if not mess.is_manager(student):
        messages.error(request, "Only the mess manager can manage members.")
        return redirect("mess:dashboard", pk=mess.pk)

    if request.method == "POST":
        action = request.POST.get("action")
        target = Student.objects.filter(pk=request.POST.get("student")).first()

        if target is None:
            messages.error(request, "No such student.")

        elif action == "add":
            if target.mess_id is not None:
                messages.error(
                    request,
                    f"{target.username} is already in another mess.")
            else:
                target.mess = mess
                target.save(update_fields=["mess"])
                messages.success(request, f"{target.username} added.")

        elif action == "remove":
            if target.pk == mess.manager_id:
                # Removing yourself would leave the mess with no manager and
                # nobody able to fix it.
                messages.error(
                    request,
                    "The manager cannot leave their own mess. Hand the mess "
                    "to someone else in /admin/ first.")
            elif target.mess_id != mess.pk:
                messages.error(request, "They are not in this mess.")
            else:
                target.mess = None
                target.save(update_fields=["mess"])
                messages.success(
                    request,
                    f"{target.username} removed. Their past meal and expense "
                    f"records stay in the khata — removing a person must not "
                    f"change what everyone already owes.")

        return redirect("mess:members", pk=mess.pk)

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


@login_required
def delete_meal(request, pk, meal_id):
    """
    Remove a wrong meal entry. Manager only, POST only.

    Corrections are exactly why a digital khata beats a notebook — but only
    one person should be able to make them, or the numbers stop meaning
    anything.
    """
    student = _student(request)
    mess = get_object_or_404(Mess, pk=pk)

    if not mess.is_manager(student):
        messages.error(request, "Only the mess manager can remove entries.")
        return redirect("mess:dashboard", pk=mess.pk)

    if request.method == "POST":
        DailyMeal.objects.filter(pk=meal_id, mess=mess).delete()
        messages.success(request, "Entry removed.")

    return redirect("mess:dashboard", pk=mess.pk)
