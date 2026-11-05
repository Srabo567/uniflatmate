from django.contrib import admin

from .models import Area


@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    list_display = ("name", "zone", "is_student_hub", "latitude", "longitude")
    list_filter = ("zone", "is_student_hub")
    list_editable = ("is_student_hub",)
    search_fields = ("name",)
