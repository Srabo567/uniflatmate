from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    # where LOGIN_REDIRECT_URL points — routes by account type
    path("welcome/", views.after_login, name="after_login"),

    # sign-up
    path("signup/", views.signup_choice, name="signup"),
    path("signup/student/", views.signup, name="signup_student"),
    path("signup/owner/", views.signup_owner, name="signup_owner"),

    # email verification
    path("verify/sent/", views.verify_sent, name="verify_sent"),
    path("verify/<uidb64>/<token>/", views.verify, name="verify"),

    # profile
    path("profile/", views.profile, name="profile"),
    path("profile/edit/", views.profile_edit, name="profile_edit"),

    # roommate requests
    path("requests/", views.requests_inbox, name="requests_inbox"),
    path("requests/send/<int:student_id>/", views.send_request, name="send_request"),
    path("requests/<int:request_id>/respond/", views.respond_request, name="respond_request"),

    # accepted requests — this is where contact details are revealed
    path("connections/", views.connections, name="connections"),
    path("connections/<int:request_id>/remove/",
         views.remove_connection, name="remove_connection"),
]
