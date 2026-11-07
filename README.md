# UniFlatMate

A roommate matching and shared-living platform for university students.

Django 5.2 LTS · Python · SQLite · Bootstrap 5 · Leaflet

**CSE 302 — Object Oriented Programming II Lab, University of Asia Pacific**

| Member | ID | Owns |
|---|---|---|
| Farhana Tabassum Srabony | 24101166 | `accounts/` · `matching/` |
| Samia Sarwar | 24101175 | `listings/` |
| Most. Tazkiya Moufat Mif | 24101168 | `mess/` · `locations/` |
| Shuvro Das | 24101187 | `reviews/` · templates & CSS |

---

## Run it

```bash
python -m venv venv
venv\Scripts\activate             # Windows
source venv/bin/activate          # Mac / Linux

pip install -r requirements.txt

copy .env.example .env            # Windows   (cp on Mac / Linux)
#   open .env and put any long random string as SECRET_KEY

python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser

python manage.py seed_universities    # 22 Dhaka campuses
python manage.py seed_areas           # 46 Dhaka areas
python manage.py seed_demo_mess       # a demo mess with meal records
python manage.py seed_demo            # 14 demo students, 2 owners

python manage.py test
python manage.py runserver
```

Open http://127.0.0.1:8000/ — log in as `demo_nusrat`, password `demo12345`.

---

## What works right now

| Feature | URL |
|---|---|
| Home | `/` |
| Student sign-up with university-email check | `/accounts/signup/student/` |
| Owner sign-up | `/accounts/signup/owner/` |
| Email verification link | `/accounts/verify/<uid>/<token>/` |
| Log in / log out | `/accounts/login/` |
| Forgot password | `/accounts/password_reset/` |
| My profile | `/accounts/profile/` |
| Edit lifestyle preferences | `/accounts/profile/edit/` |
| Compatibility matches, filtered by department | `/matching/` |
| Roommate requests, accept / decline | `/accounts/requests/` |
| Connections — contact details after accepting | `/accounts/connections/` |
| Admin | `/admin/` |

---

## Apps

| App | Status | Models |
|---|---|---|
| `accounts` | done | University, UniversityEmailDomain, User, Student, Owner, RoommateRequest |
| `matching` | done | none — the compatibility score needs no table |
| `locations` | done | Area |
| `listings` | empty, waiting | Amenity, Listing, ListingPhoto, SeatRequest |
| `mess` | done | Mess, DailyMeal, MessExpense |
| `reviews` | empty, waiting | Review |

The four empty apps are already in `INSTALLED_APPS`, so each person only has to
write their models and uncomment one line in `uniflatmate/urls.py`.

---

## Build order — this matters

Everything points at `accounts`, so it goes first. Then:

```
accounts (done)  →  locations  →  listings  →  mess
                                       ↘  reviews
```

**Two rules that stop the repository breaking:**

1. Run `makemigrations` for **your own app only** —
   `python manage.py makemigrations listings`. Different apps write to
   different folders, so your migration file can never collide with anyone
   else's. Commit the migration file; it is code, not junk.

2. Only edit files in your own folder. If you need something changed in
   someone else's, message them.

### One thing left over for later

`accounts/models.py` has a `mess` foreign key that is commented out, because
`mess.Mess` does not exist yet. Once Tazkiya's `mess` app is merged,
uncomment those four lines, put `"mess"` back on `list_display` in
`accounts/admin.py`, and run `makemigrations accounts`. That is its own small
commit.

---

## Three things worth knowing about `accounts`

**Student and Owner are both User.** Django calls this multi-table
inheritance: it creates three tables, and the child table's primary key is
also a foreign key to `user`. One consequence — a person is a Student *or* an
Owner, never both.

**"Verified student" means the email domain, not the roll number.** Anyone can
type a roll number. `University.allows_email()` checks the address ends with
one of that university's real domains, and the account stays inactive until
the emailed link is clicked.

**Accepting a roommate request is what reveals contact details.**
`RoommateRequest.contact_visible_to()` — the rule lives on the model, never in
a template, so no future page can forget the check. Nothing is stored as a
"revealed" flag, which is why removing a connection hides the details again
immediately.

---

## Tests

```bash
python manage.py test
```

Covering sign-up and the email-domain rule, the compatibility score, and the
contact-reveal boundary — hidden while pending, hidden after declining,
visible to both parties after accepting, never visible to a third student, and
gone again after a removal.
