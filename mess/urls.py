from django.urls import path

from . import views

app_name = "mess"

urlpatterns = [
    path("", views.my_mess, name="my_mess"),
    path("<int:pk>/", views.dashboard, name="dashboard"),
    path("<int:pk>/meal/", views.add_meal, name="add_meal"),
    path("<int:pk>/expense/", views.add_expense, name="add_expense"),
    path("<int:pk>/members/", views.members, name="members"),
    path("<int:pk>/meal/<int:meal_id>/delete/",
         views.delete_meal, name="delete_meal"),
]
