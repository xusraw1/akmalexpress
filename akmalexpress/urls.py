from django.urls import path
from .views import *

urlpatterns = [
    path('', index, name='index'),
    path('create/product/', create_product, name='create_product'),
    path('create/order/', create_order, name='create_order'),
    path('order/', order_list, name='orders'),
    path('order/<slug:slug>/change/', change_order, name='change_order'),
    path('order/<slug:slug>/delete/', delete_order, name='delete_order'),
    path('order/<slug:slug>/detail/', detail_order, name='detail_order'),

    path('toggle_status/<int:user_id>/', toggle_status, name='toggle_status'),
    path('create/admin/', create_admin, name='create_admin'),
    path('profile/<str:user>/', profile_view, name='profile'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
]
