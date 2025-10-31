from django.urls import path
from .views import deposit_ftct_view

urlpatterns = [
    path('', deposit_ftct_view, name='deposit_ftct'),
]
