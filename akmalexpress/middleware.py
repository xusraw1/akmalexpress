from django.conf import settings
from django.shortcuts import render
from django.utils import translation

from .i18n import normalize_language, translate_html_content


class LanguageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # LocaleMiddleware (runs before us) determines language from URL/cookie.
        # Do not override it before URL resolving, otherwise i18n_patterns can break.
        request_language = normalize_language(
            getattr(request, 'LANGUAGE_CODE', None) or translation.get_language()
        )
        request.LANGUAGE_CODE = request_language
        request.session[settings.LANGUAGE_COOKIE_NAME] = request_language
        request.session['site_language'] = request_language

        response = self.get_response(request)

        language = normalize_language(
            getattr(request, 'LANGUAGE_CODE', None) or translation.get_language() or request_language
        )
        response.set_cookie(settings.LANGUAGE_COOKIE_NAME, language, max_age=60 * 60 * 24 * 365)
        response.set_cookie('site_language', language, max_age=60 * 60 * 24 * 365)

        content_type = response.get('Content-Type', '')
        if language == 'uz' and content_type.startswith('text/html') and hasattr(response, 'content'):
            charset = getattr(response, 'charset', None) or 'utf-8'
            try:
                html = response.content.decode(charset)
                html = translate_html_content(html, language)
                response.content = html.encode(charset)
                response['Content-Length'] = str(len(response.content))
            except Exception:
                return response

        return response


class NoIndexPrivateRoutesMiddleware:
    """Mark private pages as noindex to keep them out of search engines."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        admin_prefix = f"/{getattr(settings, 'ADMIN_URL', 'admin/')}".replace('//', '/')
        staff_login_prefix = f"/{getattr(settings, 'STAFF_LOGIN_URL', 'staff-login/')}".replace('//', '/')
        admin_prefix_no_slash = admin_prefix.rstrip('/')
        staff_login_prefix_no_slash = staff_login_prefix.rstrip('/')
        protected_prefixes = (
            '/admin/',
            admin_prefix,
            admin_prefix_no_slash,
            staff_login_prefix,
            staff_login_prefix_no_slash,
            '/login/',
            '/logout/',
            '/panel/',
            '/panel',
            '/notifications/',
            '/order/',
            '/create/',
            '/toggle_status/',
            '/delete_admin/',
            '/profile/',
        )

        accepts_html = 'text/html' in (request.META.get('HTTP_ACCEPT', '') or '')
        is_private_route = request.path.startswith(protected_prefixes)
        if response.status_code == 404 and accepts_html and not is_private_route:
            response = render(request, '404.html', status=404)

        if request.path.startswith(protected_prefixes):
            response['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
        return response
