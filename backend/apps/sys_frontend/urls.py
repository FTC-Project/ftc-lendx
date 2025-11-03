from django.urls import path
from .views import deposit_ftct_view, deposit_status_view, deposit_ftct_data

urlpatterns = [
    path("", deposit_ftct_view, name="deposit_ftct"),
    path("status/<str:task_id>/", deposit_status_view, name="deposit_status"),
    path("data", deposit_ftct_data, name="deposit_ftct_data"),
]
