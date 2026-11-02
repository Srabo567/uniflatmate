"""
accounts/views.py  —  WORKED EXAMPLE (sign-up + email verification)

Three views:
    signup        create the account, email a verification link
    verify_sent   "check your email" page
    verify        the link target — activates the account

No extra packages. Django's own token generator does the cryptography.
"""

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import NoReverseMatch, reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from matching.services import calculate_compatibility

from .forms import (
    OwnerSignUpForm, StudentProfileForm, StudentSignUpForm,
)
from .models import Owner, RoommateRequest, Student

User = get_user_model()


def _send_verification_email(request, user):
    """
    Build a one-time link and email it.

    uid   = the user's primary key, base64-encoded so it is URL-safe
    token = a signed, expiring token tied to this user

    The token is NOT stored in the database. Django regenerates it from the
    user's password hash, last_login and is_active, so it stops working the
    moment the account is activated. That is why it cannot be reused.
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


@login_required
def after_login(request):
    """
    Where you land straight after logging in.

    LOGIN_REDIRECT_URL can only be one fixed URL, so it used to send
    everybody to /matching/ — and an OWNER would arrive on a page saying
    "student profile needed", two seconds after signing in. A dead end as a
    welcome.

    So the setting points here instead, and this view decides.
    """
    if Owner.objects.filter(pk=request.user.pk).exists():
        # listings app তৈরি হলে owner কে সরাসরি dashboard এ পাঠাবে।
        # এখনো হয়নি, তাই reverse() পারে কিনা দেখে নিই — নাহলে
        # প্রতিটা owner login এ NoReverseMatch হয়ে সাইট ভেঙে যেত।
        try:
            reverse("listings:dashboard")
            return redirect("listings:dashboard")
        except NoReverseMatch:
            return redirect("accounts:profile")
    if Student.objects.filter(pk=request.user.pk).exists():
        return redirect("matching:match_list")
    # staff, or an account that is neither — the admin is what they want
    return redirect("accounts:profile")


def signup(request):
    """Student registration."""
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = StudentSignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            _send_verification_email(request, user)
            return redirect("accounts:verify_sent")
    else:
        form = StudentSignUpForm()

    return render(request, "accounts/signup.html", {"form": form})


def verify_sent(request):
    return render(request, "accounts/verify_sent.html")


def verify(request, uidb64, token):
    """
    The link target. Activates the account if the token checks out.
    """
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.is_verified = True
        user.save(update_fields=["is_active", "is_verified"])
        return render(request, "accounts/verify_done.html", {"username": user.username})

    return render(request, "accounts/verify_failed.html")


# =========================================================================
#  Owner sign-up
# =========================================================================

def signup_choice(request):
    """Student or owner? Two different accounts, two different forms."""
    if request.user.is_authenticated:
        return redirect("home")
    return render(request, "accounts/signup_choice.html")


def signup_owner(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = OwnerSignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            _send_verification_email(request, user)
            return redirect("accounts:verify_sent")
    else:
        form = OwnerSignUpForm()

    return render(request, "accounts/signup_owner.html", {"form": form})


# =========================================================================
#  Profile
# =========================================================================

@login_required
def profile(request):
    student = (Student.objects
               .filter(pk=request.user.pk)
               .select_related("university")
               .first())
    owner = Owner.objects.filter(pk=request.user.pk).first() if student is None else None
    return render(request, "accounts/profile.html",
                  {"student": student, "owner": owner})


@login_required
def profile_edit(request):
    student = Student.objects.filter(pk=request.user.pk).first()
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


# =========================================================================
#  Roommate requests  (Student -> Student. THE OTHER STUDENT DECIDES.)
# =========================================================================

@login_required
def send_request(request, student_id):
    """
    Send a roommate request. POST only — a GET must never change data.
    """
    sender = Student.objects.filter(pk=request.user.pk).first()
    receiver = get_object_or_404(Student, pk=student_id)

    if sender is None or sender.pk == receiver.pk:
        return redirect("matching:match_list")

    if request.method != "POST":
        return redirect("matching:match_list")

    # get_or_create relies on the unique constraint in the model, so a
    # double-click cannot create two rows.
    req, created = RoommateRequest.objects.get_or_create(
        sender=sender, receiver=receiver,
        defaults={"message": request.POST.get("message", "")[:500]},
    )
    if created:
        messages.success(request, f"Request sent to {receiver.username}.")
    else:
        messages.info(request, f"You already sent {receiver.username} a request.")

    return redirect("matching:match_list")


@login_required
def requests_inbox(request):
    """Requests received and sent, side by side."""
    student = Student.objects.filter(pk=request.user.pk).first()
    if student is None:
        return render(request, "matching/not_a_student.html")

    received = (RoommateRequest.objects
                .filter(receiver=student)
                .select_related("sender", "sender__university"))
    sent = (RoommateRequest.objects
            .filter(sender=student)
            .select_related("receiver", "receiver__university"))

    return render(request, "accounts/requests.html", {
        "received": received, "sent": sent,
    })


@login_required
def connections(request):
    """
    The people who accepted you, and the people you accepted — with their
    contact details.

    This page is the point of the whole request flow. Accepting used to
    change a status and leave two students with no way to reach each other.

    SECURITY NOTE: the rows are built from student.connections(), which
    already restricts to this student's own accepted requests. The
    contact_visible_to() check below is therefore belt and braces — but it
    stays, because the day someone changes that queryset, this is what
    stops a phone number escaping.
    """
    student = Student.objects.filter(pk=request.user.pk).first()
    if student is None:
        return render(request, "matching/not_a_student.html")

    rows = []
    for req in student.connections():
        if not req.contact_visible_to(student):
            continue                      # should never happen; see above
        other = req.other_party(student)
        rows.append({
            "request": req,
            "other": other,
            "score": calculate_compatibility(student, other),
        })

    rows.sort(key=lambda r: r["score"], reverse=True)
    return render(request, "accounts/connections.html",
                  {"student": student, "connections": rows})


@login_required
def remove_connection(request, request_id):
    """
    Undo a connection. POST only.

    Sets the status back to DECLINED, which immediately re-hides both
    sides' contact details — contact_visible_to() is evaluated fresh on
    every page load, so there is no stale "revealed" flag to clean up.

    Either party may do this, not just the receiver. If you accepted
    someone and it turns out badly, you must not need their permission to
    cut the connection. Because of the unique constraint on
    (sender, receiver), the declined row stays and that pair cannot start
    over — the removal doubles as a block.
    """
    student = Student.objects.filter(pk=request.user.pk).first()
    req = get_object_or_404(RoommateRequest, pk=request_id)

    if student is None or not req.involves(student):
        messages.error(request, "That connection is not yours to remove.")
        return redirect("accounts:connections")

    if request.method == "POST":
        req.status = RoommateRequest.Status.DECLINED
        req.save(update_fields=["status"])
        other = req.other_party(student)
        messages.success(
            request,
            f"Connection with {other.username} removed. Their contact "
            f"details are no longer visible to you, and yours are hidden "
            f"from them.",
        )

    return redirect("accounts:connections")


@login_required
def respond_request(request, request_id):
    """
    Accept or decline. Only the RECEIVER may answer — that is the whole
    point of this request type, and it is enforced here, not in the
    template.
    """
    student = Student.objects.filter(pk=request.user.pk).first()
    req = get_object_or_404(RoommateRequest, pk=request_id)

    if student is None or req.receiver_id != student.pk:
        messages.error(request, "That request is not yours to answer.")
        return redirect("accounts:requests_inbox")

    action = request.POST.get("action")
    if request.method == "POST" and action in {"accept", "decline"}:
        req.status = (RoommateRequest.Status.ACCEPTED if action == "accept"
                      else RoommateRequest.Status.DECLINED)
        req.save(update_fields=["status"])

        if action == "accept":
            # Send them straight where the contact details now are. An
            # accept that drops you back on the same page, with the same
            # list, is what made this feel like it did nothing.
            messages.success(
                request,
                f"You and {req.sender.username} are connected — "
                f"their contact details are below.",
            )
            return redirect("accounts:connections")

        messages.success(request, "Request declined.")

    return redirect("accounts:requests_inbox")
