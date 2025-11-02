from django.urls import path
from .views import terms_of_service_view

urlpatterns = [
    path("tos/", terms_of_service_view, name="terms_of_service"),
]
