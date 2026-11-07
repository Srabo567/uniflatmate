from django.urls import path

from . import views

app_name = "reviews"

urlpatterns = [
    path("owner/<int:owner_id>/", views.owner_reviews, name="owner_reviews"),
    path("owner/<int:owner_id>/write/", views.write_review, name="write_review"),
    path("owner/<int:owner_id>/delete/", views.delete_review, name="delete_review"),
]
