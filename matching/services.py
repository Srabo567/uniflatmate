"""The compatibility score.

Plain Python — no library, no machine learning, no training data. Every
line can be explained.

The maths lives here and not in views.py, so tests can run it without a
browser.
"""

from decimal import Decimal

# What each factor is worth. These add up to 100.
WEIGHTS = {
    "smoking": 30,      # heaviest: the most common cause of conflict
    "sleep": 25,
    "study": 20,
    "budget": 25,
}

# Two students count as budget-compatible within this many taka.
BUDGET_TOLERANCE = Decimal("1500.00")

# Below this, the page shows a warning instead of a match.
WARNING_THRESHOLD = 50


def calculate_compatibility(a, b):
    """Score how well two students would share a room, 0 to 100.

    Each factor is scored on its own and then weighted, so adding a new
    one later means one block here and one line in WEIGHTS.
    """
    score = 0

    # 1. Smoking — agreeing matters more than the habit itself
    if a.smokes == b.smokes:
        score += WEIGHTS["smoking"]

    # 2. Sleep schedule
    if a.sleeps_early == b.sleeps_early:
        score += WEIGHTS["sleep"]

    # 3. Study environment
    if a.study_at_home == b.study_at_home:
        score += WEIGHTS["study"]

    # 4. Budget — partial marks, because money is a range not a yes/no.
    #    abs() so swapping the two students cannot change the answer.
    gap = abs(a.budget - b.budget)
    if gap <= BUDGET_TOLERANCE:
        closeness = 1 - (gap / BUDGET_TOLERANCE)
        score += int(WEIGHTS["budget"] * closeness)

    return score


def is_recommended(score):
    """True if this pair should be shown as a match, not a warning."""
    return score >= WARNING_THRESHOLD


def describe_breakdown(a, b):
    """Why the score is what it is — a list the template can loop over.

    People trust a score much more when they can see the reasoning.
    """
    budget_gap = abs(a.budget - b.budget)

    return [
        ("Smoking habit", a.smokes == b.smokes),
        ("Sleep schedule", a.sleeps_early == b.sleeps_early),
        ("Study environment", a.study_at_home == b.study_at_home),
        ("Budget range", budget_gap <= BUDGET_TOLERANCE),
    ]


def find_matches(student, candidates, limit=10):
    """Score one student against many others, best first."""
    results = []

    for other in candidates:
        if other.pk == student.pk:
            continue                  # never match someone with themselves

        score = calculate_compatibility(student, other)
        results.append({
            "student": other,
            "score": score,
            "recommended": is_recommended(score),
            "breakdown": describe_breakdown(student, other),
        })

    results.sort(key=lambda row: row["score"], reverse=True)
    return results[:limit]
