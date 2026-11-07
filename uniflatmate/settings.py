"""
Django settings for UniFlatMate.
Django 5.2 LTS
"""

from pathlib import Path

from decouple import config
from django.contrib.messages import constants as message_constants

BASE_DIR = Path(__file__).resolve().parent.parent

# --- Security -------------------------------------------------------------
SECRET_KEY = config("SECRET_KEY", default="dev-only-key-change-me")
DEBUG = config("DEBUG", default=True, cast=bool)
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

# --- Applications ---------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # UniFlatMate apps — one owner each
    "accounts",     # University, User, Student, Owner, RoommateRequest
    "locations",    # Area — shared reference data, seeded
    "listings",     # Listing, SeatRequest  (+ distance search)
    "mess",         # Mess, DailyMeal, MessExpense  (+ meal rate)
    "matching",     # compatibility score — logic only, no models
    "reviews",      # Review
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "uniflatmate.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                # ours: tells every template whether the listings module is
                # wired up yet, and whether this user is an owner
                "accounts.context_processors.navigation",
            ],
        },
    },
]

WSGI_APPLICATION = "uniflatmate.wsgi.application"

# --- Database -------------------------------------------------------------
# SQLite while building. Switching to PostgreSQL later changes ONLY this
# block — every model and every query stays exactly the same.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# --- Custom user model ----------------------------------------------------
# MUST be set before the very first migration. Changing it afterwards is
# genuinely painful, which is why it is here from day one.
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Localisation ---------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Dhaka"
USE_I18N = True
USE_TZ = True

# --- Static & media -------------------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Auth redirects -------------------------------------------------------
# Not a fixed page: accounts/views.after_login decides where to send a
# student, an owner and a staff account. A single URL here meant owners
# landed on "student profile needed" the moment they logged in.
LOGIN_REDIRECT_URL = "/accounts/welcome/"
LOGOUT_REDIRECT_URL = "/"
LOGIN_URL = "/accounts/login/"

# --- Messages -------------------------------------------------------------
# Django tags error messages "error"; Bootstrap's class is "alert-danger".
# Without this remap, every error flash renders unstyled.
MESSAGE_TAGS = {message_constants.ERROR: "danger"}

# --- Email ----------------------------------------------------------------
# Verification links print to the terminal while developing — no SMTP setup,
# no real email account needed. Swap for a real backend before deployment.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "noreply@uniflatmate.local"
