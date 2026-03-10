from datetime import datetime, timedelta

from django.db.models import Q
from django.utils import timezone

from .i18n import normalize_language
from .models import Order

TRACK_NOTICE_DISMISS_KEY = 'admin_track_notice_dismissed_until'


def language_context(request):
    session = getattr(request, 'session', {})
    current_language = normalize_language(
        getattr(request, 'LANGUAGE_CODE', None) or session.get('site_language'),
    )
    return {
        'current_lang': current_language,
    }


def admin_track_notice_context(request):
    """Expose stale orders without track numbers for staff/superadmin users."""
    user = getattr(request, 'user', None)
    if user is None or not getattr(user, 'is_authenticated', False):
        return {
            'admin_track_notice_count': 0,
            'admin_track_notice_orders': [],
            'admin_track_notice_banner_count': 0,
            'admin_track_notice_banner_orders': [],
        }

    is_staff = getattr(user, 'is_staff', False)
    is_superuser = getattr(user, 'is_superuser', False)

    if not (is_staff or is_superuser):
        return {
            'admin_track_notice_count': 0,
            'admin_track_notice_orders': [],
            'admin_track_notice_banner_count': 0,
            'admin_track_notice_banner_orders': [],
        }

    reminder_date = timezone.localdate() - timedelta(days=2)

    if is_superuser:
        # Superadmin sees ALL stale orders across all users
        stale_qs = Order.objects.filter(
            order_date__lte=reminder_date,
            status__in=[Order.Status.ACCEPTED, Order.Status.ORDERED, Order.Status.TRANSIT],
        ).filter(Q(track_number__isnull=True) | Q(track_number=''))
    else:
        # Staff sees only their own stale orders
        stale_qs = Order.objects.filter(
            user=user,
            order_date__lte=reminder_date,
            status__in=[Order.Status.ACCEPTED, Order.Status.ORDERED, Order.Status.TRANSIT],
        ).filter(Q(track_number__isnull=True) | Q(track_number=''))

    stale_orders = stale_qs.select_related('user').order_by('order_date')[:20]
    stale_count = stale_qs.count()

    banner_count = stale_count
    banner_orders = stale_orders

    if stale_count == 0:
        request.session.pop(TRACK_NOTICE_DISMISS_KEY, None)
        return {
            'admin_track_notice_count': 0,
            'admin_track_notice_orders': [],
            'admin_track_notice_banner_count': 0,
            'admin_track_notice_banner_orders': [],
        }

    dismissed_until_raw = request.session.get(TRACK_NOTICE_DISMISS_KEY)
    if dismissed_until_raw:
        try:
            dismissed_until = datetime.fromisoformat(dismissed_until_raw)
            if timezone.is_naive(dismissed_until):
                dismissed_until = timezone.make_aware(dismissed_until, timezone.get_current_timezone())
        except Exception:
            dismissed_until = None

        if dismissed_until and timezone.now() < dismissed_until:
            banner_count = 0
            banner_orders = []
        elif dismissed_until and timezone.now() >= dismissed_until:
            request.session.pop(TRACK_NOTICE_DISMISS_KEY, None)

    return {
        'admin_track_notice_count': stale_count,
        'admin_track_notice_orders': stale_orders,
        'admin_track_notice_banner_count': banner_count,
        'admin_track_notice_banner_orders': banner_orders,
    }
