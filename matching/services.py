"""
matching/services.py  —  WORKED EXAMPLE (the unique feature)

UniFlatMate's compatibility score. Deliberately plain Python: no framework,
no machine learning, no libraries. That is a strength, not a shortcut — you
can explain every line in the viva, and it needs no training data.

Business logic lives in services.py, NOT in views.py. A view handles the web
request and nothing else. Keeping the algorithm here means tests.py can run
it without a browser.
"""

from decimal import Decimal

# What each factor is worth. They must total 100.
# Tuning these numbers IS the "iterative tuning" claim in the CEP table, so
# keep a note of why you chose them.
WEIGHTS = {
    "smoking": 30,      # heaviest: the most common cause of conflict
    "sleep": 25,
    "study": 20,
    "budget": 25,
}

# Two students count as budget-compatible within this many taka.
BUDGET_TOLERANCE = Decimal("1500.00")

# Below this, the UI shows a warning instead of a match.
WARNING_THRESHOLD = 50


def calculate_compatibility(a, b):
    """
    Score how well two students would share a room, 0 to 100.

    Takes two Student objects, returns an int.

    Each factor is scored independently then weighted, so adding a new
    factor later means one block here and one entry in WEIGHTS — nothing
    else in the project changes.
    """
    score = 0

    # 1. Smoking — agreement matters more than the habit itself
    if a.smokes == b.smokes:
        score += WEIGHTS["smoking"]

    # 2. Sleep schedule
    if a.sleeps_early == b.sleeps_early:
        score += WEIGHTS["sleep"]

    # 3. Study environment
    if a.study_at_home == b.study_at_home:
        score += WEIGHTS["study"]

    # 4. Budget — partial credit, because money is a spectrum.
    #    abs() so the order of the two students never changes the result.
    gap = abs(a.budget - b.budget)
    if gap <= BUDGET_TOLERANCE:
        closeness = 1 - (gap / BUDGET_TOLERANCE)
        score += int(WEIGHTS["budget"] * closeness)

    return score


def is_recommended(score):
    """True if this pair should be shown as a match rather than a warning."""
    return score >= WARNING_THRESHOLD


def describe_breakdown(a, b):
    """
    Explain WHY the score is what it is, for the result page.

    Returns (label, matched) pairs a template can loop over. People trust a
    score far more when they can see the reasoning, and it demos much better
    than a bare number.
    """
    return [
        ("Smoking habit", a.smokes == b.smokes),
        ("Sleep schedule", a.sleeps_early == b.sleeps_early),
        ("Study environment", a.study_at_home == b.study_at_home),
        ("Budget range", abs(a.budget - b.budget) <= BUDGET_TOLERANCE),
    ]


def find_matches(student, candidates, limit=10):
    """
    Score a student against many candidates, best first.

    `candidates` is a queryset or list of Students.
    Returns a list of dicts, highest score first.
    """
    results = []
    for other in candidates:
        if other.pk == student.pk:
            continue                      # never match someone with themselves
        score = calculate_compatibility(student, other)
        results.append({
            "student": other,
            "score": score,
            "recommended": is_recommended(score),
            "breakdown": describe_breakdown(student, other),
        })

    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:limit]
