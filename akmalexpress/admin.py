from django.contrib import admin
from .models import Product, ProductDetail, Order


def superuser_admin_only(request):
    """Allow access to Django admin only for active superusers."""
    return request.user.is_active and request.user.is_superuser


admin.site.has_permission = superuser_admin_only


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['id', 'product_name', 'product_quantity', 'product_price', 'store', 'created_at']
    list_filter = ['store', 'created_at', 'updated_at']
    list_editable = ['product_name', 'store', 'product_quantity', 'product_price']


@admin.register(Order)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['id', 'product', 'first_name', 'phone1', 'status']
    list_filter = ['created_at', 'updated_at', 'user']
    list_editable = ['product', 'first_name', 'phone1', 'status']
