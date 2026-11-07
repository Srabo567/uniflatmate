"""The match page.

The shape used everywhere in this project: URL -> view -> service ->
template. The view only fetches and renders; the scoring is in
services.py.
"""

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render

from accounts.models import RoommateRequest, Student

from .services import find_matches


@login_required
def match_list(request):
    """Show the logged-in student their best roommate matches."""
    student = Student.objects.filter(pk=request.user.pk).first()
    if student is None:
        return render(request, "matching/not_a_student.html")

    # Other students, same university, same gender. Filtered in the query,
    # not in the template.
    candidates = (
        Student.objects
        .filter(university=student.university, gender=student.gender)
        .exclude(pk=student.pk)
        .select_related("university")
    )

    # Optional filter from the address bar: ?dept=CSE
    # An unknown department is ignored rather than returning an empty page.
    department = request.GET.get("dept") or ""
    if department in Student.Department.values:
        candidates = candidates.filter(department=department)
    else:
        department = ""

    # Score everyone, then paginate. A small limit here would silently hide
    # people after the best few.
    results = find_matches(student, candidates, limit=200)

    # One query for everyone already asked, so the template can disable the
    # button instead of letting someone send twice.
    already_requested = set(
        RoommateRequest.objects
        .filter(sender=student)
        .values_list("receiver_id", flat=True)
    )

    # Paginate last: the sort is by score, which Python computed.
    total = len(results)
    page = Paginator(results, 9).get_page(request.GET.get("page"))

    # keep the filter when going to page 2
    query = request.GET.copy()
    query.pop("page", None)

    return render(request, "matching/match_list.html", {
        "student": student,
        "page_obj": page,
        "results": page.object_list,
        "total": total,
        "already_requested": already_requested,
        "departments": Student.Department.choices,
        "selected_department": department,
        "querystring": query.urlencode(),
    })
