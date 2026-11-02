"""
matching/views.py  —  WORKED EXAMPLE (a complete, working feature)

This is the end-to-end pattern for the whole project: URL -> view ->
service -> template. Copy this shape for listings, mess and reviews.

Notice how thin the view is. It fetches data, calls a service, renders a
template. No arithmetic lives here.
"""

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render

from accounts.models import RoommateRequest, Student
from .services import find_matches


@login_required
def match_list(request):
    """Show the logged-in student their best roommate matches."""

    # request.user is a User. Is it a Student?
    student = Student.objects.filter(pk=request.user.pk).first()
    if student is None:
        return render(request, "matching/not_a_student.html")

    # Candidates: other students, same university, same gender.
    # Gender filtering is applied HERE, in the query — not in the template.
    candidates = (
        Student.objects
        .filter(university=student.university, gender=student.gender)
        .exclude(pk=student.pk)
        .select_related("university")           # avoids N+1 queries
    )

    # To enforce the "verified student network" objective strictly, add:
    #     .filter(is_verified=True)
    # It is left off here so students you add by hand in the admin (which
    # defaults is_verified to False) still appear while you are building.

    # Optional filter: ?dept=CSE
    # Now that Department is a fixed choice list, the value can be validated
    # against it — an unknown ?dept= is ignored instead of silently
    # returning an empty page.
    department = request.GET.get("dept") or ""
    if department in Student.Department.values:
        candidates = candidates.filter(department=department)
    else:
        department = ""

    # Scored in full, then paginated — 9 per page. The old limit=20
    # silently hid everyone after the twentieth best match.
    results = find_matches(student, candidates, limit=200)

    # One query for every pairing already requested, so the template can
    # disable the button instead of letting someone send twice.
    already_requested = set(
        RoommateRequest.objects
        .filter(sender=student)
        .values_list("receiver_id", flat=True)
    )

    # Paginated after scoring, because the sort is by score and that is
    # computed in Python, not by the database.
    total = len(results)
    page = Paginator(results, 9).get_page(request.GET.get("page"))

    query = request.GET.copy()
    query.pop("page", None)

    return render(request, "matching/match_list.html", {
        "student": student,
        "page_obj": page,
        "results": page.object_list,
        "total": total,
        "already_requested": already_requested,
        # for the filter dropdown
        "departments": Student.Department.choices,
        "selected_department": department,
        "querystring": query.urlencode(),
    })
