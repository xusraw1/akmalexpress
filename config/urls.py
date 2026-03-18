import re

from django.contrib import admin
from django.http import HttpResponseNotFound
from django.shortcuts import redirect
from django.urls import path, include, re_path
from django.conf.urls.i18n import i18n_patterns
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve as serve_static
from akmalexpress.views import robots_txt, custom_404_debug

handler404 = 'akmalexpress.views.custom_404'


def redirect_legacy_ru_prefix(request, legacy_path=''):
    cleaned = (legacy_path or '').lstrip('/')
    destination = f'/{cleaned}' if cleaned else '/'
    return redirect(destination, permanent=False)


def redirect_admin_without_slash(request):
    return redirect(f'/{settings.ADMIN_URL}', permanent=False)


def hide_default_admin(request):
    return HttpResponseNotFound('Not found')

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls, name='django_admin'),
    path(settings.ADMIN_URL.rstrip('/'), redirect_admin_without_slash, name='django_admin_redirect'),
    path('admin/', hide_default_admin, name='hidden_admin'),
    path('admin', hide_default_admin, name='hidden_admin_no_slash'),
    re_path(r'^ru/?$', redirect_legacy_ru_prefix, name='legacy_ru_root'),
    re_path(r'^ru/(?P<legacy_path>.*)$', redirect_legacy_ru_prefix, name='legacy_ru_path'),
    path('i18n/', include('django.conf.urls.i18n')),
    path('robots.txt', robots_txt, name='robots_txt'),
]

urlpatterns += i18n_patterns(
    path('', include('akmalexpress.urls')),
    prefix_default_language=False,
)

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += [path('<path:unmatched_path>', custom_404_debug, name='debug_404')]
elif settings.SERVE_MEDIA_FILES:
    media_prefix = settings.MEDIA_URL.strip('/')
    if media_prefix:
        urlpatterns += [
            re_path(
                rf'^{re.escape(media_prefix)}/(?P<path>.*)$',
                serve_static,
                {'document_root': settings.MEDIA_ROOT},
                name='media_serve',
            )
        ]
