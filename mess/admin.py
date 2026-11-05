from django.contrib import admin

from .models import DailyMeal, Mess, MessExpense


@admin.register(Mess)
class MessAdmin(admin.ModelAdmin):
    list_display = ("mess_name", "listing", "manager", "member_count")
    search_fields = ("mess_name",)


@admin.register(DailyMeal)
class DailyMealAdmin(admin.ModelAdmin):
    list_display = ("student", "mess", "meal_date", "meal_count", "added_by")
    list_filter = ("mess", "meal_date")


@admin.register(MessExpense)
class MessExpenseAdmin(admin.ModelAdmin):
    list_display = ("mess", "payer", "amount", "expense_type", "spent_on")
    list_filter = ("mess", "expense_type")
