from django.http import JsonResponse
from backend.apps.users.models import TelegramUser
from backend.apps.scoring.models import TrustScoreSnapshot

def score_profile(request):
    try:
        user_id = int(request.GET.get("user_id"))
    except (TypeError, ValueError):
        return JsonResponse({"error": "Invalid user_id"}, status=400)

    try:
        user = TelegramUser.objects.get(id=user_id)
    except TelegramUser.DoesNotExist:
        return JsonResponse({"error": "User not found"}, status=404)

    snapshot = TrustScoreSnapshot.objects.filter(user=user).order_by("-created_at").first()
    if not snapshot:
        return JsonResponse({"error": "No score available"}, status=404)

    return JsonResponse({
        "user": user.id,
        "trust_score": float(snapshot.trust_score),
        "risk_category": snapshot.risk_category,
        "created_at": snapshot.created_at.isoformat(),
    })
