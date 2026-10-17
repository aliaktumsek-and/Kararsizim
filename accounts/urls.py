from django.urls import path

from . import views

urlpatterns = [
    path("giris/", views.login_page, name="login"),
    path("kayit/", views.register_page, name="register"),
]
