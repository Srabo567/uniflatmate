from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

urlpatterns = [
    path("", TemplateView.as_view(template_name="home.html"), name="home"),
    path("admin/", admin.site.urls),
    # Our sign-up / verification routes come FIRST, so they win over the
    # built-in ones on any shared path. Django matches top to bottom.
    path("accounts/", include("accounts.urls")),
    path("accounts/", include("django.contrib.auth.urls")),   # login/logout for free
    path("matching/", include("matching.urls")),

    path("listings/", include("listings.urls")),
    path("mess/", include("mess.urls")),
    path("reviews/", include("reviews.urls")),
]

# Uploaded photos. Django's dev server does NOT serve MEDIA_ROOT on its
# own — without these two lines every listing photo is a broken image icon
# and nothing appears in the console to tell you why.
#
# DEBUG only, on purpose: in production a real web server (nginx, or object
# storage) serves these, and Django should never be in that path.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
