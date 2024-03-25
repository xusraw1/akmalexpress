from django.urls import path
from .views import *

urlpatterns = [
    path('', index, name='index'),
    path('create/product/', create_product, name='create_product'),
    path('create/order/', create_order, name='create_order'),
    path('order/', order_list, name='orders'),
    path('order/<slug:slug>/change/', change_order, name='change_order'),

    path('profile/<str:user>/', profile_view, name='profile'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
]
