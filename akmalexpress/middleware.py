from django.utils.translation import activate

from .i18n import normalize_language, translate_html_content


class LanguageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        requested_language = request.GET.get('lang')
        session_language = request.session.get('site_language')
        cookie_language = request.COOKIES.get('site_language')

        language = normalize_language(requested_language or session_language or cookie_language or 'ru')
        request.session['site_language'] = language
        request.LANGUAGE_CODE = language
        activate(language)

        response = self.get_response(request)
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
