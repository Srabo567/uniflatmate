"""Rooms posted by owners, and the seat requests students send for them."""

from django.core.exceptions import ValidationError
from django.db import models

MAX_PHOTO_MB = 5
ALLOWED_PHOTO_TYPES = {".jpg", ".jpeg", ".png", ".webp"}


def validate_photo(f):
    """Reject photos that are too big or not an image."""
    if f.size > MAX_PHOTO_MB * 1024 * 1024:
        raise ValidationError(f"Keep photos under {MAX_PHOTO_MB} MB.")

    name = getattr(f, "name", "") or ""
    if "." not in name:
        raise ValidationError("Use a JPG, PNG or WEBP image.")

    extension = "." + name.rsplit(".", 1)[1].lower()
    if extension not in ALLOWED_PHOTO_TYPES:
        raise ValidationError("Use a JPG, PNG or WEBP image.")


class Amenity(models.Model):
    """Something a place has or does not have: fridge, geyser, lift."""

    class Category(models.TextChoices):
        UTILITY = "UTILITY", "Utilities"
        COMFORT = "COMFORT", "Comfort"
        KITCHEN = "KITCHEN", "Kitchen"
        SAFETY = "SAFETY", "Safety"

    name = models.CharField(max_length=50, unique=True)
    category = models.CharField(
        max_length=10, choices=Category.choices, default=Category.COMFORT,
    )
    icon = models.CharField(max_length=30, blank=True)

    class Meta:
        ordering = ["category", "name"]
        verbose_name_plural = "amenities"

    def __str__(self):
        return self.name


class Listing(models.Model):
    """A room, or a set of seats, offered by an owner."""

    class Washroom(models.TextChoices):
        ATTACHED = "A", "Attached"
        COMMON = "C", "Common"
        SHARED_ONE = "S", "Shared with one other room"

    class Furnishing(models.TextChoices):
        UNFURNISHED = "U", "Unfurnished"
        SEMI = "S", "Semi-furnished (bed, almirah)"
        FURNISHED = "F", "Furnished"

    class Cooking(models.TextChoices):
        PIPED_GAS = "G", "Piped gas line"
        CYLINDER = "C", "Gas cylinder"
        INDUCTION = "I", "Induction cooker"
        INFRARED = "R", "Infrared cooker"
        NONE = "N", "No cooking facility"

    # who and where
    owner = models.ForeignKey(
        "accounts.Owner", on_delete=models.CASCADE, related_name="listings",
    )
    area = models.ForeignKey(
        "locations.Area", on_delete=models.PROTECT, related_name="listings",
    )
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)

    # the basics
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True, max_length=2000)
    rent = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Monthly rent in BDT. Information only — paid to the owner.",
    )

    # what students ask about
    floor = models.PositiveSmallIntegerField(help_text="0 for ground floor.")
    washroom = models.CharField(max_length=1, choices=Washroom.choices)
    furnishing = models.CharField(
        max_length=1, choices=Furnishing.choices, default=Furnishing.SEMI,
    )
    cooking = models.CharField(
        max_length=1, choices=Cooking.choices, default=Cooking.PIPED_GAS,
    )

    seats_total = models.PositiveSmallIntegerField(default=1)
    seats_available = models.PositiveSmallIntegerField(default=1)
    available_from = models.DateField()

    amenities = models.ManyToManyField(Amenity, blank=True, related_name="listings")

    is_female_only = models.BooleanField(default=False)
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        # No coordinates means the listing never shows up in a distance
        # search, so fall back to the centre of its area.
        if self.latitude is None or self.longitude is None:
            self.latitude = self.area.latitude
            self.longitude = self.area.longitude
        super().save(*args, **kwargs)

    @classmethod
    def visible_to(cls, user):
        """Listings this user is allowed to see. Filtered in the database."""
        listings = cls.objects.filter(is_available=True)

        is_female = getattr(user, "gender", None) == "F"
        if not is_female:
            listings = listings.filter(is_female_only=False)

        return listings

    @property
    def cover_photo(self):
        photos = list(self.photos.all())
        if not photos:
            return None

        for photo in photos:
            if photo.is_cover:
                return photo
        return photos[0]

    @property
    def is_full(self):
        return self.seats_available == 0

    def __str__(self):
        return f"{self.title} — {self.area}"


class ListingPhoto(models.Model):
    """One photo of a listing. A listing can have several."""

    listing = models.ForeignKey(
        Listing, on_delete=models.CASCADE, related_name="photos",
    )
    image = models.ImageField(
        upload_to="listings/%Y/%m/", validators=[validate_photo],
    )
    caption = models.CharField(max_length=100, blank=True)
    is_cover = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.caption or f"Photo {self.pk}"


class SeatRequest(models.Model):
    """A student asks an owner for a seat. The owner decides."""

    class Status(models.TextChoices):
        PENDING = "P", "Pending"
        ACCEPTED = "A", "Accepted"
        REJECTED = "R", "Rejected"

    student = models.ForeignKey(
        "accounts.Student", on_delete=models.CASCADE, related_name="seat_requests",
    )
    listing = models.ForeignKey(
        Listing, on_delete=models.CASCADE, related_name="requests",
    )
    status = models.CharField(
        max_length=1, choices=Status.choices, default=Status.PENDING,
    )
    message = models.TextField(blank=True, max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # One request per student per listing.
            models.UniqueConstraint(
                fields=["student", "listing"], name="one_seat_request_per_pair",
            ),
        ]

    def contact_visible_to(self, user):
        """Phone numbers show only after an accept, and only to those two."""
        if user is None:
            return False
        if self.status != self.Status.ACCEPTED:
            return False
        return user.pk in (self.student_id, self.listing.owner_id)

    def __str__(self):
        return f"{self.student} -> {self.listing} ({self.get_status_display()})"
