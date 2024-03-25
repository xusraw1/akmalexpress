from django import forms
from .models import Product, ProductDetail, Order


class CreateProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['product_name', 'product_quantity', 'product_price_currency', 'product_price', 'store', 'link',
                  'image1', 'image2']


class CreateOrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['receipt_number', 'first_name', 'last_name', 'phone1', 'phone2', 'debt', 'description', 'status']


class ChangeOrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['product', 'receipt_number', 'first_name', 'last_name', 'phone1', 'phone2', 'debt', 'description',
                  'status']