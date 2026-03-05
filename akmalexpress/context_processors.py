from .i18n import normalize_language


def language_context(request):
    current_language = normalize_language(getattr(request, 'LANGUAGE_CODE', None) or request.session.get('site_language'))
    return {
        'current_lang': current_language,
    }
