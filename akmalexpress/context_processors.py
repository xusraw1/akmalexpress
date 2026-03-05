from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from .i18n import normalize_language
from .models import Order


def language_context(request):
    current_language = normalize_language(getattr(request, 'LANGUAGE_CODE', None) or request.session.get('site_language'))
    return {
        'current_lang': current_language,
    }


def admin_track_notice_context(request):
    """Expose count of stale orders without track numbers for staff users."""
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated or not user.is_staff or user.is_superuser:
        return {
            'admin_track_notice_count': 0,
        }

    reminder_date = timezone.localdate() - timedelta(days=2)
    pending_count = (
        Order.objects.filter(
            user=user,
            order_date__lte=reminder_date,
            status__in=[Order.Status.NO, Order.Status.berildi, Order.Status.yolda],
        )
        .filter(Q(track_number__isnull=True) | Q(track_number=''))
        .count()
    )

    return {
        'admin_track_notice_count': pending_count,
    }
