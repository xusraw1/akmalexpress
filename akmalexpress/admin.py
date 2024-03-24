from django.contrib import admin
from .models import Product, ProductDetail, Order


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['id', 'product_name', 'product_quantity', 'product_price', 'store', 'created_at']
    list_filter = ['store', 'created_at', 'updated_at']
    list_editable = ['product_name', 'store', 'product_quantity', 'product_price']
