from django.urls import path
from .views import *

urlpatterns = [
    path('', index, name='index'),
    path('create/product/', create_product, name='create_product'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
]
