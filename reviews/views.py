"""Writing and reading reviews of an owner.

Only a student whose seat request that owner accepted may review them.
Without that rule anyone could review anyone, and the rating would mean
nothing.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import Owner, Student
from listings.models import SeatRequest

from .forms import ReviewForm
from .models import Review


def get_student(request):
    """The Student account for this user, or None."""
    return Student.objects.filter(pk=request.user.pk).first()


def may_review(student, owner):
    """True if this owner ever accepted a seat request from this student."""
    return SeatRequest.objects.filter(
        student=student,
        listing__owner=owner,
        status=SeatRequest.Status.ACCEPTED,
    ).exists()


def owner_reviews(request, owner_id):
    """Public page: every review of one owner."""
    owner = get_object_or_404(Owner, pk=owner_id)
    reviews = Review.objects.filter(owner=owner).select_related("author")

    student = None
    if request.user.is_authenticated:
        student = get_student(request)

    mine = None
    can_review = False
    if student is not None:
        mine = reviews.filter(author=student).first()
        can_review = mine is None and may_review(student, owner)

    return render(request, "reviews/owner_reviews.html", {
        "owner": owner,
        "reviews": reviews,
        "student": student,
        "my_review": mine,
        "can_review": can_review,
    })


@login_required
def write_review(request, owner_id):
    """Write a new review, or edit the one you already wrote."""
    student = get_student(request)
    owner = get_object_or_404(Owner, pk=owner_id)

    if student is None:
        return render(request, "matching/not_a_student.html")

    if not may_review(student, owner):
        messages.error(
            request,
            "You can review an owner only after they have accepted one of "
            "your seat requests.",
        )
        return redirect("reviews:owner_reviews", owner_id=owner.pk)

    # instance=None means a new row; instance=existing means an edit. One
    # view covers both.
    existing = Review.objects.filter(author=student, owner=owner).first()

    if request.method == "POST":
        form = ReviewForm(request.POST, instance=existing)

        if form.is_valid():
            review = form.save(commit=False)
            review.author = student
            review.owner = owner
            review.save()          # save() refreshes the owner's rating

            messages.success(request, "Thanks — your review is posted.")
            return redirect("reviews:owner_reviews", owner_id=owner.pk)
    else:
        form = ReviewForm(instance=existing)

    return render(request, "reviews/review_form.html", {
        "form": form,
        "owner": owner,
        "editing": existing is not None,
    })


@login_required
def delete_review(request, owner_id):
    """Remove your own review. POST only."""
    student = get_student(request)
    owner = get_object_or_404(Owner, pk=owner_id)
    review = Review.objects.filter(author=student, owner=owner).first()

    if request.method == "POST" and review is not None:
        review.delete()            # delete() refreshes the owner's rating
        messages.success(request, "Your review was removed.")

    return redirect("reviews:owner_reviews", owner_id=owner.pk)
