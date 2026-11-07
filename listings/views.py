"""Pages for owners (post a room, answer requests) and students (search).

The view fetches, services.py calculates, the template shows. No distance
maths here.
"""

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, F, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import Owner, Student

from .forms import (
    ListingForm, ListingPhotoFormSet, ListingSearchForm, SeatRequestForm,
)
from .models import Listing, SeatRequest
from .services import listings_near_university


# ---------------------------------------------------------------- helpers

def get_owner(request):
    """The Owner account for this user, or None."""
    return Owner.objects.filter(pk=request.user.pk).first()


def get_student(request):
    """The Student account for this user, or None."""
    return Student.objects.filter(pk=request.user.pk).first()


def not_an_owner(request):
    messages.error(request, "That page is for owner accounts.")
    return redirect("accounts:profile")


def area_coords_json():
    """{area id: [lat, lon]} so the map re-centres when an area is picked."""
    from locations.models import Area

    coords = {}
    for area in Area.objects.all():
        coords[area.pk] = [area.latitude, area.longitude]

    return json.dumps(coords)


# ------------------------------------------------------------------ owner

@login_required
def dashboard(request):
    """Everything one owner has, on one page."""
    owner = get_owner(request)
    if owner is None:
        return not_an_owner(request)

    # annotate() counts the pending requests inside the same query. Counting
    # in the template would be one extra query per listing.
    listings = (
        Listing.objects
        .filter(owner=owner)
        .select_related("area")
        .prefetch_related("photos", "amenities")
        .annotate(pending_count=Count(
            "requests",
            filter=Q(requests__status=SeatRequest.Status.PENDING),
        ))
    )

    total_pending = 0
    live_count = 0
    seats_free = 0

    for listing in listings:
        total_pending += listing.pending_count
        if listing.is_available:
            live_count += 1
            seats_free += listing.seats_available

    return render(request, "listings/dashboard.html", {
        "owner": owner,
        "listings": listings,
        "total_pending": total_pending,
        "live_count": live_count,
        "seats_free": seats_free,
    })


@login_required
def listing_create(request):
    owner = get_owner(request)
    if owner is None:
        return not_an_owner(request)

    if request.method == "POST":
        form = ListingForm(request.POST)
        # request.FILES is required, or the photos are silently dropped.
        photos = ListingPhotoFormSet(request.POST, request.FILES)

        # Both have to be valid before anything is written, so we never get
        # a listing whose photos failed.
        if form.is_valid() and photos.is_valid():
            listing = form.save(commit=False)
            listing.owner = owner
            listing.save()
            form.save_m2m()           # amenities, needed after commit=False

            photos.instance = listing
            photos.save()

            messages.success(request, "Listing posted.")
            return redirect("listings:detail", pk=listing.pk)
    else:
        form = ListingForm(initial={"available_from": timezone.localdate()})
        photos = ListingPhotoFormSet()

    return render(request, "listings/listing_form.html", {
        "form": form,
        "photos": photos,
        "mode": "create",
        "area_coords": area_coords_json(),
    })


@login_required
def listing_edit(request, pk):
    owner = get_owner(request)
    if owner is None:
        return not_an_owner(request)

    # owner=owner inside the lookup, so someone else's listing is a 404.
    listing = get_object_or_404(Listing, pk=pk, owner=owner)

    if request.method == "POST":
        form = ListingForm(request.POST, instance=listing)
        photos = ListingPhotoFormSet(
            request.POST, request.FILES, instance=listing)

        if form.is_valid() and photos.is_valid():
            form.save()
            photos.save()
            messages.success(request, "Listing updated.")
            return redirect("listings:detail", pk=listing.pk)
    else:
        form = ListingForm(instance=listing)
        photos = ListingPhotoFormSet(instance=listing)

    return render(request, "listings/listing_form.html", {
        "form": form,
        "photos": photos,
        "listing": listing,
        "mode": "edit",
        "area_coords": area_coords_json(),
    })


@login_required
def listing_toggle(request, pk):
    """Hide a listing, or put it back. POST only."""
    owner = get_owner(request)
    if owner is None:
        return not_an_owner(request)

    listing = get_object_or_404(Listing, pk=pk, owner=owner)

    if request.method == "POST":
        listing.is_available = not listing.is_available
        listing.save(update_fields=["is_available"])

        if listing.is_available:
            messages.success(request, "Listing is live again.")
        else:
            messages.success(
                request, "Listing hidden — students can no longer find it.")

    return redirect("listings:dashboard")


@login_required
def seat_requests(request):
    """The owner's inbox of students who want a seat."""
    owner = get_owner(request)
    if owner is None:
        return not_an_owner(request)

    found = (
        SeatRequest.objects
        .filter(listing__owner=owner)
        .select_related("student__university", "listing__area", "listing__owner")
    )

    rows = []
    pending = 0
    for seat_request in found:
        rows.append({
            "request": seat_request,
            "contact_visible": seat_request.contact_visible_to(request.user),
        })
        if seat_request.status == SeatRequest.Status.PENDING:
            pending += 1

    return render(request, "listings/seat_requests.html", {
        "owner": owner,
        "rows": rows,
        "pending": pending,
    })


@login_required
def respond_seat_request(request, pk):
    """Accept or reject. The owner decides."""
    owner = get_owner(request)
    if owner is None:
        return not_an_owner(request)

    seat_request = get_object_or_404(SeatRequest, pk=pk, listing__owner=owner)
    action = request.POST.get("action")

    if request.method != "POST" or action not in {"accept", "reject"}:
        return redirect("listings:seat_requests")

    if action == "reject":
        seat_request.status = SeatRequest.Status.REJECTED
        seat_request.save(update_fields=["status"])
        messages.success(request, "Request rejected.")
        return redirect("listings:seat_requests")

    listing = seat_request.listing

    if listing.seats_available < 1:
        messages.error(request, "No seats left on that listing.")
        return redirect("listings:seat_requests")

    seat_request.status = SeatRequest.Status.ACCEPTED
    seat_request.save(update_fields=["status"])

    # F() subtracts inside the database. Reading the number into Python and
    # writing it back loses one of two accepts that arrive together.
    Listing.objects.filter(pk=listing.pk).update(
        seats_available=F("seats_available") - 1)
    listing.refresh_from_db(fields=["seats_available"])

    if listing.seats_available == 0:
        listing.is_available = False
        listing.save(update_fields=["is_available"])

    messages.success(
        request,
        f"Accepted. {seat_request.student.username} can now see your contact "
        f"number, and you can see theirs.",
    )
    return redirect("listings:seat_requests")


# ---------------------------------------------------------------- student

@login_required
def search(request):
    """Seats near your campus."""
    student = get_student(request)
    if student is None:
        return render(request, "matching/not_a_student.html")

    form = ListingSearchForm(request.GET or None)
    radius = 3
    max_rent = None
    washroom = ""
    female_only = False

    if form.is_valid():
        radius = int(form.cleaned_data["radius_km"])
        max_rent = form.cleaned_data.get("max_rent")
        washroom = form.cleaned_data.get("washroom") or ""
        female_only = form.cleaned_data.get("female_only") or False

    results = listings_near_university(student.university, radius, student)

    # These run after the service's own security filter, never instead of it.
    if max_rent is not None:
        results = [r for r in results if r["listing"].rent <= max_rent]
    if washroom:
        results = [r for r in results if r["listing"].washroom == washroom]
    if female_only:
        results = [r for r in results if r["listing"].is_female_only]

    already = set(
        SeatRequest.objects
        .filter(student=student)
        .values_list("listing_id", flat=True)
    )

    # Paginate last: the sort is by distance, which Python computed.
    total = len(results)
    page = Paginator(results, 9).get_page(request.GET.get("page"))

    # keep the filters when going to page 2
    query = request.GET.copy()
    query.pop("page", None)

    return render(request, "listings/search.html", {
        "student": student,
        "form": form,
        "page_obj": page,
        "results": page.object_list,
        "total": total,
        "radius": radius,
        "already_requested": already,
        "querystring": query.urlencode(),
    })


@login_required
def detail(request, pk):
    """One listing in full."""
    viewer = request.user

    listing = get_object_or_404(
        Listing.objects
        .select_related("area", "owner")
        .prefetch_related("photos", "amenities"),
        pk=pk,
    )

    # An owner always sees their own listing, even hidden or full. For
    # everyone else a listing they may not see is a 404, not a blank page.
    is_my_listing = listing.owner_id == viewer.pk
    if not is_my_listing:
        allowed = Listing.visible_to(viewer).filter(pk=pk).exists()
        if not allowed:
            raise Http404("No listing matches the given query.")

    student = get_student(request)

    existing = None
    contact_visible = False
    if student is not None:
        existing = SeatRequest.objects.filter(
            student=student, listing=listing).first()
    if existing is not None:
        contact_visible = existing.contact_visible_to(viewer)

    return render(request, "listings/listing_detail.html", {
        "listing": listing,
        "student": student,
        "is_my_listing": is_my_listing,
        "existing_request": existing,
        "contact_visible": contact_visible,
        "form": SeatRequestForm(),
    })


@login_required
def request_seat(request, pk):
    """A student asks for a seat. POST only — a GET must not change data."""
    student = get_student(request)
    if student is None:
        return render(request, "matching/not_a_student.html")

    listing = get_object_or_404(Listing.visible_to(student), pk=pk)

    if request.method != "POST":
        return redirect("listings:detail", pk=listing.pk)

    if listing.seats_available < 1:
        messages.error(request, "That listing has no seats left.")
        return redirect("listings:detail", pk=listing.pk)

    form = SeatRequestForm(request.POST)
    message = ""
    if form.is_valid():
        message = form.cleaned_data["message"]

    # get_or_create relies on the unique constraint, so a double click
    # cannot make two rows.
    seat_request, created = SeatRequest.objects.get_or_create(
        student=student, listing=listing, defaults={"message": message},
    )

    if created:
        messages.success(
            request,
            "Request sent. The owner decides — you will see their contact "
            "number here if they accept.",
        )
    else:
        messages.info(request, "You have already requested this seat.")

    return redirect("listings:detail", pk=listing.pk)


@login_required
def my_seat_requests(request):
    """What the student asked for, and what came back."""
    student = get_student(request)
    if student is None:
        return render(request, "matching/not_a_student.html")

    found = (
        SeatRequest.objects
        .filter(student=student)
        .select_related("listing__area", "listing__owner")
        .prefetch_related("listing__photos")
    )

    rows = []
    for seat_request in found:
        rows.append({
            "request": seat_request,
            "contact_visible": seat_request.contact_visible_to(request.user),
        })

    return render(request, "listings/my_requests.html", {
        "student": student,
        "rows": rows,
    })
