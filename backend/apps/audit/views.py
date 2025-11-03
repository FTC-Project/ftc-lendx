from django.http import HttpResponse
from django.shortcuts import render


def terms_of_service_view(request):
    """Render the Terms of Service page using Django templates and static assets."""
    return render(request, "audit/terms_of_service.html")
