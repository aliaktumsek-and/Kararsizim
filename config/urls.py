from django.contrib import admin
from django.urls import include, path

from polls import views as poll_views

urlpatterns = [
    path("", poll_views.index, name="index"),
    path("anket/<int:poll_id>/", poll_views.detail_page, name="poll-page"),
    path("olustur/", poll_views.create_page, name="create"),
    path("", include("accounts.urls")),
    path("api/polls/", include("polls.urls")),
    path("api/auth/", include("accounts.api_urls")),
    path("admin/", admin.site.urls),
]
