from django import forms
from .models import Product, ProductDetail, Order


class CreateProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['product_name', 'product_quantity', 'product_price_currency', 'product_price', 'store', 'link',
                  'image1', 'image2']
