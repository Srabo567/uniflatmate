from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    Owner, RoommateRequest, Student, University, UniversityEmailDomain, User,
)


class EmailDomainInline(admin.TabularInline):
    """
    Edit a university's allowed domains on the university's own page.

    An inline is the right shape here: a domain never makes sense on its
    own, only as part of a university.
    """
    model = UniversityEmailDomain
    extra = 1


@admin.register(University)
class UniversityAdmin(admin.ModelAdmin):
    list_display = ("short_code", "name", "domains", "latitude", "longitude")
    search_fields = ("short_code", "name")
    inlines = [EmailDomainInline]

    @admin.display(description="allowed email domains")
    def domains(self, obj):
        return obj.domain_list or "— none set, sign-up closed —"

    def get_queryset(self, request):
        # prefetch, or the list page runs one query per university
        return super().get_queryset(request).prefetch_related("email_domains")


@admin.register(UniversityEmailDomain)
class UniversityEmailDomainAdmin(admin.ModelAdmin):
    """Also registered on its own, so you can search every domain at once."""
    list_display = ("domain", "university", "note")
    list_filter = ("university",)
    search_fields = ("domain",)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """Registering a model here is what makes it appear in /admin/."""
    list_display = ("username", "email", "gender", "is_verified", "is_staff")
    list_filter = ("gender", "is_verified", "is_staff")


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("username", "university", "department", "batch",
                    "budget", "smokes", "sleeps_early")   # mess যোগ হলে এখানে ফেরাবে
    # batch is a property, so filter on the real columns behind it
    list_filter = ("university", "department", "batch_year", "batch_season",
                   "smokes", "sleeps_early")
    search_fields = ("username",)


@admin.register(Owner)
class OwnerAdmin(admin.ModelAdmin):
    list_display = ("username", "owner_rating", "contact_number")


@admin.register(RoommateRequest)
class RoommateRequestAdmin(admin.ModelAdmin):
    list_display = ("sender", "receiver", "status", "created_at")
    list_filter = ("status",)
