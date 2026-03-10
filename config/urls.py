from django.contrib import admin
from django.http import HttpResponseNotFound
from django.shortcuts import redirect
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from akmalexpress.views import robots_txt, custom_404_debug

handler404 = 'akmalexpress.views.custom_404'

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path(settings.ADMIN_URL.rstrip('/'), lambda request: redirect(f'/{settings.ADMIN_URL}', permanent=False)),
    path('admin/', lambda request: HttpResponseNotFound('Not found')),
    path('admin', lambda request: HttpResponseNotFound('Not found')),
    path('robots.txt', robots_txt, name='robots_txt'),
    path('', include('akmalexpress.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += [path('<path:unmatched_path>', custom_404_debug, name='debug_404')]
