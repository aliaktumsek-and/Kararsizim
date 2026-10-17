from django.urls import path

from . import views

urlpatterns = [
    path("", views.poll_list, name="api-poll-list"),
    path("<int:poll_id>/", views.poll_detail, name="api-poll-detail"),
]
