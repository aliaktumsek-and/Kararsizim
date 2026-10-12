from django.contrib import admin
from django.urls import path

from polls import views as poll_views

urlpatterns = [
    path("", poll_views.index, name="index"),
    path("admin/", admin.site.urls),
]
