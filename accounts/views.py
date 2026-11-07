"""Sign-up, email verification, profile, and roommate requests.

Django's own token generator does the cryptography — no extra packages.
"""

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from matching.services import calculate_compatibility

from .forms import OwnerSignUpForm, StudentProfileForm, StudentSignUpForm
from .models import Owner, RoommateRequest, Student

User = get_user_model()


# ---------------------------------------------------------------- helpers

def get_student(request):
    """The Student account for this user, or None."""
    return Student.objects.filter(pk=request.user.pk).first()


def send_verification_email(request, user):
    """Email a one-time activation link.

    uid is the primary key, base64 encoded so it is safe in a URL. The
    token is not stored anywhere — Django rebuilds it from the password
    hash, last_login and is_active, so it stops working once the account
    is activated. That is why the link only works once.
    """
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    link = request.build_absolute_uri(
        reverse("accounts:verify", kwargs={"uidb64": uid, "token": token})
    )

    send_mail(
        subject="Confirm your UniFlatMate account",
        message=(
            f"Hi {user.username},\n\n"
            f"Confirm your university email to activate your account:\n\n"
            f"{link}\n\n"
            f"If you did not sign up, ignore this message.\n"
        ),
        from_email=None,              # uses DEFAULT_FROM_EMAIL
        recipient_list=[user.email],
        fail_silently=False,
    )


# ------------------------------------------------------- sign-up and login

@login_required
def after_login(request):
    """Where you land right after logging in.

    LOGIN_REDIRECT_URL can only be one fixed address, so it points here and
    this view decides. Otherwise an owner would land on the student match
    page and be told they need a student profile.
    """
    if Owner.objects.filter(pk=request.user.pk).exists():
        return redirect("listings:dashboard")

    if Student.objects.filter(pk=request.user.pk).exists():
        return redirect("matching:match_list")

    return redirect("accounts:profile")


def signup_choice(request):
    """Student or owner? Two different accounts, two different forms."""
    if request.user.is_authenticated:
        return redirect("home")
    return render(request, "accounts/signup_choice.html")


def signup(request):
    """Student registration."""
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = StudentSignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            send_verification_email(request, user)
            return redirect("accounts:verify_sent")
    else:
        form = StudentSignUpForm()

    return render(request, "accounts/signup.html", {"form": form})


def signup_owner(request):
    """Owner registration."""
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = OwnerSignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            send_verification_email(request, user)
            return redirect("accounts:verify_sent")
    else:
        form = OwnerSignUpForm()

    return render(request, "accounts/signup_owner.html", {"form": form})


def verify_sent(request):
    return render(request, "accounts/verify_sent.html")


def verify(request, uidb64, token):
    """The link target. Activates the account if the token checks out."""
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is None:
        return render(request, "accounts/verify_failed.html")

    if not default_token_generator.check_token(user, token):
        return render(request, "accounts/verify_failed.html")

    user.is_active = True
    user.is_verified = True
    user.save(update_fields=["is_active", "is_verified"])

    return render(request, "accounts/verify_done.html",
                  {"username": user.username})


# ---------------------------------------------------------------- profile

@login_required
def profile(request):
    student = (Student.objects
               .filter(pk=request.user.pk)
               .select_related("university")
               .first())

    owner = None
    if student is None:
        owner = Owner.objects.filter(pk=request.user.pk).first()

    return render(request, "accounts/profile.html",
                  {"student": student, "owner": owner})


@login_required
def profile_edit(request):
    student = get_student(request)
    if student is None:
        return redirect("accounts:profile")

    if request.method == "POST":
        form = StudentProfileForm(request.POST, instance=student)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated.")
            return redirect("accounts:profile")
    else:
        form = StudentProfileForm(instance=student)

    return render(request, "accounts/profile_edit.html", {"form": form})


# ------------------------------------------------------- roommate requests

@login_required
def send_request(request, student_id):
    """Send a roommate request. POST only."""
    sender = get_student(request)
    receiver = get_object_or_404(Student, pk=student_id)

    if sender is None or sender.pk == receiver.pk:
        return redirect("matching:match_list")

    if request.method != "POST":
        return redirect("matching:match_list")

    message = request.POST.get("message", "")[:500]

    # get_or_create relies on the unique constraint, so a double click
    # cannot make two rows.
    roommate_request, created = RoommateRequest.objects.get_or_create(
        sender=sender, receiver=receiver, defaults={"message": message},
    )

    if created:
        messages.success(request, f"Request sent to {receiver.username}.")
    else:
        messages.info(request, f"You already sent {receiver.username} a request.")

    return redirect("matching:match_list")


@login_required
def requests_inbox(request):
    """Requests received and sent, side by side."""
    student = get_student(request)
    if student is None:
        return render(request, "matching/not_a_student.html")

    received = (RoommateRequest.objects
                .filter(receiver=student)
                .select_related("sender", "sender__university"))

    sent = (RoommateRequest.objects
            .filter(sender=student)
            .select_related("receiver", "receiver__university"))

    return render(request, "accounts/requests.html", {
        "received": received,
        "sent": sent,
    })


@login_required
def respond_request(request, request_id):
    """Accept or decline. Only the receiver may answer."""
    student = get_student(request)
    roommate_request = get_object_or_404(RoommateRequest, pk=request_id)

    if student is None or roommate_request.receiver_id != student.pk:
        messages.error(request, "That request is not yours to answer.")
        return redirect("accounts:requests_inbox")

    action = request.POST.get("action")

    if request.method != "POST" or action not in {"accept", "decline"}:
        return redirect("accounts:requests_inbox")

    if action == "accept":
        roommate_request.status = RoommateRequest.Status.ACCEPTED
        roommate_request.save(update_fields=["status"])
        messages.success(
            request,
            f"You and {roommate_request.sender.username} are connected — "
            f"their contact details are below.",
        )
        # send them where the contact details actually are
        return redirect("accounts:connections")

    roommate_request.status = RoommateRequest.Status.DECLINED
    roommate_request.save(update_fields=["status"])
    messages.success(request, "Request declined.")

    return redirect("accounts:requests_inbox")


@login_required
def connections(request):
    """The people you accepted, and who accepted you — with contact details.

    connections() already returns only this student's accepted requests.
    The check below repeats that on purpose: if anyone ever changes that
    queryset, this is what stops a phone number escaping.
    """
    student = get_student(request)
    if student is None:
        return render(request, "matching/not_a_student.html")

    rows = []
    for roommate_request in student.connections():
        if not roommate_request.contact_visible_to(student):
            continue

        other = roommate_request.other_party(student)
        rows.append({
            "request": roommate_request,
            "other": other,
            "score": calculate_compatibility(student, other),
        })

    rows.sort(key=lambda row: row["score"], reverse=True)

    return render(request, "accounts/connections.html",
                  {"student": student, "connections": rows})


@login_required
def remove_connection(request, request_id):
    """Undo a connection. POST only.

    Setting the status back to declined hides both sides' details again at
    once, because nothing is stored as a "revealed" flag. Either person may
    do this — if it goes badly you should not need the other's permission.
    The unique constraint means the pair cannot start over, so removing
    also works as a block.
    """
    student = get_student(request)
    roommate_request = get_object_or_404(RoommateRequest, pk=request_id)

    if student is None or not roommate_request.involves(student):
        messages.error(request, "That connection is not yours to remove.")
        return redirect("accounts:connections")

    if request.method == "POST":
        roommate_request.status = RoommateRequest.Status.DECLINED
        roommate_request.save(update_fields=["status"])

        other = roommate_request.other_party(student)
        messages.success(
            request,
            f"Connection with {other.username} removed. Their contact "
            f"details are no longer visible to you, and yours are hidden "
            f"from them.",
        )

    return redirect("accounts:connections")
