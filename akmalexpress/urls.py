from django.urls import path
from .views import *

urlpatterns = [
    path('', index, name='index'),
    path('create/product/', create_product, name='create_product'),
    path('create/order/', create_order, name='create_order'),

    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
]
