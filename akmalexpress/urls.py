from django.conf import settings
from django.urls import path
from .views import *

urlpatterns = [
    path('', index, name='index'),
    path('about/', about_view, name='about'),
    path('contacts/', contacts_view, name='contacts'),
    path('lang/<str:lang_code>/', set_language_view, name='set_language'),
    path('create/product/', create_product, name='create_product'),
    path('create/order/', create_order, name='create_order'),
    path('order/', order_list, name='orders'),
    path('order/<slug:slug>/change/', change_order, name='change_order'),
    path('order/<slug:slug>/delete/', delete_order, name='delete_order'),
    path('order/<slug:slug>/detail/', detail_order, name='detail_order'),
    path('order/<slug:slug>/receipt/', print_receipt, name='print_receipt'),

    path('toggle_status/<int:user_id>/', toggle_status, name='toggle_status'),
    path('delete_admin/<int:user_id>/', delete_admin, name='delete_admin'),
    path('create/admin/', create_admin, name='create_admin'),
    path('profile/<str:user>/', profile_view, name='profile'),
    path(settings.STAFF_LOGIN_URL, login_view, name='staff_login'),
    path('login/', hidden_entrypoint, name='login'),
    path('logout/', logout_view, name='logout'),
]
