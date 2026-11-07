"""Variables every template gets, without each view passing them.

Registered in settings.py under TEMPLATES -> context_processors.
"""

from django.urls import NoReverseMatch, reverse


def url_exists(name):
    """True if this URL name can be resolved right now."""
    try:
        reverse(name)
        return True
    except NoReverseMatch:
        return False


def is_owner_account(user):
    """True if this user has an Owner row.

    Multi-table inheritance gives a User a .owner accessor that raises
    when the child row is not there. One cheap primary-key lookup.
    """
    try:
        user.owner
        return True
    except Exception:
        return False


def is_student_account(user):
    try:
        user.student
        return True
    except Exception:
        return False


def navigation(request):
    """What the navbar should show.

    listings_enabled exists because the listings URLs stay commented out
    in uniflatmate/urls.py until that app is written. Without the flag, a
    {% url 'listings:search' %} in base.html would break every page.
    """
    user = getattr(request, "user", None)

    is_owner = False
    is_student = False

    if user is not None and user.is_authenticated:
        is_owner = is_owner_account(user)
        if not is_owner:
            is_student = is_student_account(user)

    return {
        "listings_enabled": url_exists("listings:search"),
        "is_owner": is_owner,
        "is_student": is_student,
    }
