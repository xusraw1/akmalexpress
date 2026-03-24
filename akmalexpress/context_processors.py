"""Template context processors used across base layout."""

from django.conf import settings
from django.utils import translation

from .i18n import normalize_language

TRACK_NOTICE_DISMISS_KEY = 'admin_track_notice_dismissed_until'


def language_context(request):
    """Expose current language code for header/sidebar language switcher."""
    session = getattr(request, 'session', {})
    current_language = normalize_language(
        getattr(request, 'LANGUAGE_CODE', None)
        or session.get(settings.LANGUAGE_COOKIE_NAME)
        or session.get('site_language')
        or translation.get_language(),
    )
    return {
        'current_lang': current_language,
    }


def admin_track_notice_context(request):
    """Track reminder notifications are disabled to keep pages lightweight."""
    return {
        'admin_track_notice_count': 0,
        'admin_track_notice_orders': [],
        'admin_track_notice_banner_count': 0,
        'admin_track_notice_banner_orders': [],
    }
