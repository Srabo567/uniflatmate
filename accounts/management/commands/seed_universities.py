"""
accounts/management/commands/seed_universities.py

    python manage.py seed_universities

Loads the Dhaka universities into the database so students have something
to pick on the sign-up form.

WHY A COMMAND AND NOT THE ADMIN
    Typing twenty universities into /admin/ is twenty minutes, and you do it
    again on every laptop and every time someone deletes db.sqlite3. This
    file is the single source of truth: run it once per machine and all four
    of you have identical data.

WHY A COMMAND AND NOT A DATA MIGRATION
    A migration runs once, in order, and editing it afterwards means
    rewriting history. Reference data like this changes — a university adds
    a domain, you fix a coordinate. A command you can safely re-run is the
    better fit. It is idempotent: running it twice changes nothing, and it
    never overwrites an edit you made in the admin unless you pass --force.

------------------------------------------------------------------------
BEFORE YOUR DEMO — VERIFY THE EMAIL DOMAINS
------------------------------------------------------------------------
Each entry below is (short code, full name, latitude, longitude, domains).

The DOMAINS decide who can sign up, so a wrong one means a real student is
turned away in front of Sir. Only UAP is confirmed (it is Srabony's own
address). The rest are the universities' main institutional domains and are
a sensible starting point, but SOME UNIVERSITIES ISSUE STUDENTS A DIFFERENT
DOMAIN from the one on their website.

How to check one, in about thirty seconds:
  1. Open the university's website, find "webmail" or the student portal.
  2. Or ask one person who studies there what their university email ends in.
  3. Add it in /admin/ -> Universities -> (the university) -> Email domains.

You do NOT need to edit this file to fix one. Several domains per university
is the normal case, not the exception — add, don't replace.

The COORDINATES are approximate campus centres. They are accurate enough for
a 1–5 km radius search. To make one exact: open Google Maps, right-click the
campus, and the first item on the menu is the latitude and longitude — click
it to copy.
------------------------------------------------------------------------
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import University, UniversityEmailDomain

# (short_code, name, latitude, longitude, [domains])
UNIVERSITIES = [
    # --- public ---
    ("DU", "University of Dhaka", 23.7330, 90.3929, ["du.ac.bd"]),
    ("BUET", "Bangladesh University of Engineering & Technology",
     23.7265, 90.3925, ["buet.ac.bd"]),
    ("JnU", "Jagannath University", 23.7083, 90.4022, ["jnu.ac.bd"]),
    ("JU", "Jahangirnagar University", 23.8800, 90.2670, ["juniv.edu"]),
    ("BUP", "Bangladesh University of Professionals",
     23.8223, 90.3654, ["bup.edu.bd"]),
    ("MIST", "Military Institute of Science and Technology",
     23.8223, 90.3708, ["mist.ac.bd"]),
    ("BUTEX", "Bangladesh University of Textiles",
     23.7340, 90.3850, ["butex.edu.bd"]),
    ("SAU", "Sher-e-Bangla Agricultural University",
     23.7667, 90.3833, ["sau.edu.bd"]),

    # --- private ---
    ("UAP", "University of Asia Pacific", 23.7461, 90.3742,
     ["uap-bd.edu"]),                       # confirmed
    ("NSU", "North South University", 23.8153, 90.4255,
     ["northsouth.edu", "northsouth.ac.bd"]),
    ("BRACU", "BRAC University", 23.7747, 90.4255,
     ["bracu.ac.bd", "g.bracu.ac.bd"]),
    ("IUB", "Independent University, Bangladesh",
     23.8139, 90.4270, ["iub.edu.bd"]),
    ("AIUB", "American International University-Bangladesh",
     23.8285, 90.4250, ["aiub.edu", "student.aiub.edu"]),
    ("UIU", "United International University",
     23.8030, 90.4500, ["uiu.ac.bd"]),
    ("EWU", "East West University", 23.7650, 90.4260, ["ewubd.edu"]),
    ("DIU", "Daffodil International University",
     23.8760, 90.3200, ["diu.edu.bd"]),
    ("ULAB", "University of Liberal Arts Bangladesh",
     23.7590, 90.3570, ["ulab.edu.bd"]),
    ("AUST", "Ahsanullah University of Science and Technology",
     23.7690, 90.4070, ["aust.edu"]),
    ("BUBT", "Bangladesh University of Business and Technology",
     23.8180, 90.3570, ["bubt.edu.bd"]),
    ("SEU", "Southeast University", 23.7720, 90.4030, ["seu.edu.bd"]),
    ("IUBAT", "International University of Business Agriculture and Technology",
     23.8680, 90.3900, ["iubat.edu"]),
    ("STAMFORD", "Stamford University Bangladesh",
     23.7470, 90.3820, ["stamforduniversity.edu.bd"]),
]


class Command(BaseCommand):
    help = "Load the Dhaka universities and their allowed email domains."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force", action="store_true",
            help="Overwrite the name and coordinates of universities that "
                 "already exist. Domains are always added, never removed.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        force = options["force"]
        created_unis = updated_unis = created_domains = 0

        for code, name, lat, lon, domains in UNIVERSITIES:
            uni, created = University.objects.get_or_create(
                short_code=code,
                defaults={"name": name, "latitude": lat, "longitude": lon},
            )
            if created:
                created_unis += 1
            elif force:
                uni.name, uni.latitude, uni.longitude = name, lat, lon
                uni.save()
                updated_unis += 1

            for domain in domains:
                # get_or_create on a unique column, so re-running is safe and
                # a domain already claimed by another university is skipped
                # rather than crashing the whole import.
                _, made = UniversityEmailDomain.objects.get_or_create(
                    domain=domain.lower(), defaults={"university": uni},
                )
                if made:
                    created_domains += 1

        self.stdout.write(self.style.SUCCESS(
            f"Universities: {created_unis} added"
            + (f", {updated_unis} updated" if force else "")
            + f". Email domains: {created_domains} added."
        ))
        self.stdout.write(
            "Reminder: only UAP's domain is confirmed. Check the others in "
            "/admin/ before you demo — see the notes at the top of this file."
        )
