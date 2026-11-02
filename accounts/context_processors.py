"""
accounts/context_processors.py

A context processor adds variables to EVERY template without each view
having to pass them. Registered in settings.py under TEMPLATES ->
context_processors.

Used here for two things the navbar needs on every page.
"""

from django.urls import NoReverseMatch, reverse


def _reversible(name):
    """True if a URL name can be resolved right now."""
    try:
        reverse(name)
        return True
    except NoReverseMatch:
        return False


def navigation(request):
    """
    What to show in the navbar.

    `listings_enabled` exists because the listings URLs are commented out
    in uniflatmate/urls.py until that app's models are written. Without
    this flag, a {% url 'listings:search' %} in base.html would raise
    NoReverseMatch and take down every page on the site.

    So the owner links appear by themselves the moment someone uncomments
    that line. Nothing else to remember.
    """
    user = getattr(request, "user", None)

    is_owner = is_student = False
    if user is not None and user.is_authenticated:
        # Multi-table inheritance gives a User a .owner / .student accessor
        # that raises DoesNotExist when the child row is not there. One
        # cheap primary-key lookup each.
        try:
            user.owner
            is_owner = True
        except Exception:
            pass
        if not is_owner:
            try:
                user.student
                is_student = True
            except Exception:
                pass

    return {
        # প্রতিটা module তৈরি হলে তার link আপনাআপনি navbar এ চলে আসবে।
        # এই flag না থাকলে base.html এ এমন url থাকত যা এখনো নেই, আর
        # সাইটের সব page NoReverseMatch দিয়ে ভেঙে পড়ত।
        "listings_enabled": _reversible("listings:search"),
        "mess_enabled": _reversible("mess:my_mess"),
        "reviews_enabled": _reversible("reviews:owner_reviews") or _has("reviews"),
        "is_owner": is_owner,
        "is_student": is_student,
    }


def _has(namespace):
    """reviews:owner_reviews এর argument লাগে, তাই আলাদা করে দেখা।"""
    from django.urls import NoReverseMatch, reverse
    try:
        reverse(f"{namespace}:owner_reviews", args=[1])
        return True
    except NoReverseMatch:
        return False
