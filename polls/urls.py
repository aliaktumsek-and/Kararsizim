from django.urls import path

from . import views

urlpatterns = [
    path("", views.poll_collection, name="api-poll-list"),
    path("<int:poll_id>/", views.poll_item, name="api-poll-detail"),
    path("<int:poll_id>/vote/", views.poll_vote, name="api-poll-vote"),
    path("<int:poll_id>/close/", views.poll_close, name="api-poll-close"),
]
