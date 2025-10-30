from django.urls import path
from .views import score_profile

urlpatterns = [
    path("profile", score_profile, name="score-profile"),
]
