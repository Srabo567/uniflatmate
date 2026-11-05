"""
locations/management/commands/seed_areas.py

    python manage.py seed_areas

Loads the Dhaka neighbourhoods students actually live in.

Same reasoning as seed_universities: reference data belongs in a re-runnable
command, not typed into the admin on four separate laptops.

THE COORDINATES are the rough centre of each area — accurate to a few
hundred metres, which is all a 1–5 km radius search needs. To make one
exact: open Google Maps, right-click the spot, and the first menu item is
the latitude and longitude; click it to copy.

is_student_hub marks the areas students cluster in, which is only used to
put them at the top of the dropdown. It is a convenience, not a judgement
about the neighbourhood.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from locations.models import Area

C, N, E, O, X = "C", "N", "E", "O", "X"

# (name, zone, latitude, longitude, is_student_hub)
AREAS = [
    # --- central ---
    ("Farmgate", C, 23.7580, 90.3896, True),
    ("Green Road", C, 23.7495, 90.3855, True),
    ("Panthapath", C, 23.7520, 90.3870, True),
    ("Kalabagan", C, 23.7490, 90.3830, True),
    ("Dhanmondi", C, 23.7465, 90.3760, True),
    ("Jigatola", C, 23.7400, 90.3740, False),
    ("Science Lab", C, 23.7390, 90.3830, True),
    ("Elephant Road", C, 23.7370, 90.3860, False),
    ("Shahbagh", C, 23.7380, 90.3960, False),
    ("Moghbazar", C, 23.7480, 90.4030, False),
    ("Malibagh", C, 23.7490, 90.4120, False),
    ("Shantinagar", C, 23.7420, 90.4110, False),
    ("Tejgaon", C, 23.7640, 90.3930, True),
    ("Mohammadpur", C, 23.7650, 90.3590, True),
    ("Shyamoli", C, 23.7740, 90.3650, True),
    ("Adabor", C, 23.7740, 90.3560, False),
    ("Agargaon", C, 23.7780, 90.3790, False),

    # --- north ---
    ("Mirpur-1", N, 23.7980, 90.3540, True),
    ("Mirpur-2", N, 23.8060, 90.3620, True),
    ("Mirpur-10", N, 23.8070, 90.3690, True),
    ("Mirpur-12", N, 23.8280, 90.3660, False),
    ("Kazipara", N, 23.7940, 90.3760, True),
    ("Shewrapara", N, 23.7890, 90.3760, True),
    ("Banani", N, 23.7940, 90.4040, False),
    ("Gulshan-1", N, 23.7810, 90.4150, False),
    ("Gulshan-2", N, 23.7930, 90.4150, False),
    ("Khilkhet", N, 23.8290, 90.4190, False),
    ("Nikunja", N, 23.8260, 90.4160, False),
    ("Uttara Sector 3", N, 23.8700, 90.3990, True),
    ("Uttara Sector 10", N, 23.8760, 90.3880, True),

    # --- east ---
    ("Badda", E, 23.7810, 90.4250, True),
    ("Merul Badda", E, 23.7740, 90.4240, True),
    ("Aftabnagar", E, 23.7650, 90.4320, True),
    ("Bashundhara R/A", E, 23.8180, 90.4270, True),
    ("Rampura", E, 23.7610, 90.4190, True),
    ("Khilgaon", E, 23.7510, 90.4250, False),
    ("Mugda", E, 23.7400, 90.4330, False),

    # --- old dhaka ---
    ("Azimpur", O, 23.7290, 90.3850, True),
    ("Nilkhet", O, 23.7330, 90.3880, True),
    ("Lalbagh", O, 23.7190, 90.3880, False),
    ("Hazaribagh", O, 23.7340, 90.3690, False),
    ("Paltan", O, 23.7340, 90.4140, False),
    ("Motijheel", O, 23.7330, 90.4170, False),
    ("Jatrabari", O, 23.7100, 90.4350, False),

    # --- outer ---
    ("Savar", X, 23.8580, 90.2670, False),
    ("Ashulia", X, 23.8900, 90.3200, False),
]


class Command(BaseCommand):
    help = "Load Dhaka areas (neighbourhoods) used by listings and search."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force", action="store_true",
            help="Overwrite the coordinates and zone of areas that already "
                 "exist, instead of leaving them alone.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        force = options["force"]
        created = updated = 0

        for name, zone, lat, lon, hub in AREAS:
            area, made = Area.objects.get_or_create(
                name=name,
                defaults={"zone": zone, "latitude": lat,
                          "longitude": lon, "is_student_hub": hub},
            )
            if made:
                created += 1
            elif force:
                area.zone, area.latitude = zone, lat
                area.longitude, area.is_student_hub = lon, hub
                area.save()
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"Areas: {created} added"
            + (f", {updated} updated" if force else "")
            + f". {Area.objects.count()} in total, "
              f"{Area.objects.filter(is_student_hub=True).count()} marked as "
              f"student hubs."
        ))
