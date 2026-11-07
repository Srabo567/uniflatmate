"""
listings/admin.py

Written ahead of the models. Django imports every app's admin.py at
startup, so this file must not blow up while listings/models.py is still a
TODO — hence the try/except. Delete the guard once the models exist if you
prefer it tidy; it costs nothing to leave.
"""

from django.contrib import admin

try:
    from .models import Amenity, Listing, ListingPhoto, SeatRequest
except ImportError:          # models not written yet
    Amenity = Listing = ListingPhoto = SeatRequest = None


if Listing is not None:

    class ListingPhotoInline(admin.TabularInline):
        model = ListingPhoto
        extra = 1

    @admin.register(Amenity)
    class AmenityAdmin(admin.ModelAdmin):
        list_display = ("name", "category", "icon")
        list_filter = ("category",)
        search_fields = ("name",)

    @admin.register(Listing)
    class ListingAdmin(admin.ModelAdmin):
        list_display = ("title", "owner", "area", "rent", "floor",
                        "seats_available", "is_female_only", "is_available")
        list_filter = ("is_available", "is_female_only", "area",
                       "washroom", "furnishing", "cooking")
        search_fields = ("title", "owner__username")
        filter_horizontal = ("amenities",)
        inlines = [ListingPhotoInline]
        autocomplete_fields = ("area",)

    @admin.register(SeatRequest)
    class SeatRequestAdmin(admin.ModelAdmin):
        list_display = ("student", "listing", "status", "created_at")
        list_filter = ("status",)
        search_fields = ("student__username", "listing__title")
