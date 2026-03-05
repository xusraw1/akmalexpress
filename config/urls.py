from django.contrib import admin
from django.http import HttpResponseNotFound
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from akmalexpress.views import robots_txt

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path('admin/', lambda request: HttpResponseNotFound('Not found')),
    path('robots.txt', robots_txt, name='robots_txt'),
    path('', include('akmalexpress.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
