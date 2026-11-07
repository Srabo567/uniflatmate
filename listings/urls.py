from django.urls import path

from . import views

app_name = "listings"

urlpatterns = [
    # --- student ---
    path("", views.search, name="search"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/request/", views.request_seat, name="request_seat"),
    path("my-requests/", views.my_seat_requests, name="my_requests"),

    # --- owner ---
    path("owner/", views.dashboard, name="dashboard"),
    path("owner/new/", views.listing_create, name="create"),
    path("owner/<int:pk>/edit/", views.listing_edit, name="edit"),
    path("owner/<int:pk>/toggle/", views.listing_toggle, name="toggle"),
    path("owner/requests/", views.seat_requests, name="seat_requests"),
    path("owner/requests/<int:pk>/respond/",
         views.respond_seat_request, name="respond_seat_request"),
]
