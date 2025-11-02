from django.urls import path
from .views import deposit_ftct_view, deposit_status_view

urlpatterns = [
    path("", deposit_ftct_view, name="deposit_ftct"),
    path("status/<str:task_id>/", deposit_status_view, name="deposit_status"),
]
