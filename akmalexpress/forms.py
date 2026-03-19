from decimal import Decimal

from django import forms
from django.forms import BaseFormSet, formset_factory
from django.utils import timezone

from .models import Order, OrderAttachment, OrderItem, Product
from .view_helpers import _calculate_order_totals_payload


class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultiFileField(forms.FileField):
    widget = MultiFileInput(attrs={'multiple': True, 'accept': 'image/*'})
    max_file_size_bytes = 10 * 1024 * 1024

    def clean(self, data, initial=None):
        """Validate each uploaded file and return a normalized list."""
        if not data:
            return []

        if isinstance(data, (list, tuple)):
            files = [item for item in data if item]
        else:
            files = [data]

        cleaned_files = []
        for item in files:
            cleaned_file = super(MultiFileField, self).clean(item, initial)
            content_type = (getattr(cleaned_file, 'content_type', '') or '').lower()
            file_size = getattr(cleaned_file, 'size', 0) or 0

            if content_type and not content_type.startswith('image/'):
                raise forms.ValidationError('Можно загружать только изображения.')
            if file_size > self.max_file_size_bytes:
                raise forms.ValidationError('Размер одного фото не должен превышать 10MB.')

            cleaned_files.append(cleaned_file)

        return cleaned_files


class CreateOrderForm(forms.Form):
    receipt_number = forms.IntegerField(min_value=1, label='Квитанция')
    order_date = forms.DateField(
        label='Дата заказа',
        initial=timezone.localdate,
        widget=forms.DateInput(attrs={'type': 'date'}),
    )

    first_name = forms.CharField(max_length=100, label='Имя клиента')
    last_name = forms.CharField(max_length=100, required=False, label='Фамилия клиента')
    phone1 = forms.CharField(max_length=20, label='Телефон #1')
    phone2 = forms.CharField(max_length=20, required=False, label='Телефон #2')

    debt = forms.DecimalField(min_value=0, required=False, decimal_places=2, max_digits=17, label='Долг')
    balance = forms.DecimalField(min_value=0, required=False, decimal_places=2, max_digits=17, label='Баланс')
    manual_total = forms.DecimalField(
        min_value=0,
        required=False,
        decimal_places=2,
        max_digits=17,
        label='Итоговая сумма',
    )
    shipping_method = forms.ChoiceField(
        choices=Order.ShippingMethod.choices,
        initial=Order.ShippingMethod.AVIA,
        required=False,
        widget=forms.HiddenInput(),
        label='Тип доставки (по умолчанию)',
    )
    status = forms.ChoiceField(choices=Order.Status.choices, initial=Order.Status.ACCEPTED, label='Статус')

    usd_rate = forms.DecimalField(min_value=0.01, required=True, decimal_places=2, max_digits=17, initial=12205, label='Курс USD')
    rmb_rate = forms.DecimalField(min_value=0.01, required=True, decimal_places=2, max_digits=17, initial=1807, label='Курс RMB')
    description = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3}), label='Комментарий')

    attachments = MultiFileField(required=False, label='Фото заказа (можно несколько)')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['receipt_number'].widget.attrs.update({'placeholder': 'Например: 245'})
        self.fields['first_name'].widget.attrs.update({'placeholder': 'Имя клиента'})
        self.fields['last_name'].widget.attrs.update({'placeholder': 'Фамилия клиента'})
        self.fields['phone1'].widget.attrs.update({'placeholder': '+998 XX XXX XX XX'})
        self.fields['phone2'].widget.attrs.update({'placeholder': 'Доп. номер (опционально)'})
        self.fields['usd_rate'].widget.attrs.update(
            {
                'step': '0.01',
                'placeholder': 'Например: 12205',
                'data-exchange-rate': 'usd',
                'data-exchange-autofill': '1',
            }
        )
        self.fields['rmb_rate'].widget.attrs.update(
            {
                'step': '0.01',
                'placeholder': 'Например: 1807',
                'data-exchange-rate': 'rmb',
                'data-exchange-autofill': '1',
            }
        )
        self.fields['debt'].widget.attrs.update({'step': '0.01'})
        self.fields['balance'].widget.attrs.update({'step': '0.01'})
        self.fields['manual_total'].widget.attrs.update({'step': '0.01'})
        self.fields['description'].widget.attrs.update({'placeholder': 'Комментарий к заказу'})
        self.fields['attachments'].widget.attrs.update(
            {
                'class': 'upload-input',
                'aria-describedby': 'attachments-hint attachments-meta',
            }
        )

    @staticmethod
    def _normalize_phone(raw_value):
        if raw_value is None:
            return None

        digits = ''.join(ch for ch in str(raw_value) if ch.isdigit())
        if not digits:
            return None
        return int(digits)

    def clean(self):
        cleaned_data = super().clean()

        phone1 = self._normalize_phone(cleaned_data.get('phone1'))
        phone2 = self._normalize_phone(cleaned_data.get('phone2'))

        if phone1 is None:
            self.add_error('phone1', 'Введите корректный номер телефона.')
        cleaned_data['phone1'] = phone1
        cleaned_data['phone2'] = phone2

        shipping_method = cleaned_data.get('shipping_method') or Order.ShippingMethod.AVIA

        balance = cleaned_data.get('balance') or Decimal('0.00')
        manual_total = cleaned_data.get('manual_total')

        cleaned_data['balance'] = balance
        cleaned_data['manual_total'] = manual_total if manual_total is not None else None
        cleaned_data['shipping_method'] = shipping_method

        return cleaned_data

    def save_order(self, user):
        data = self.cleaned_data
        order = Order(
            user=user,
            receipt_number=data['receipt_number'],
            order_date=data['order_date'],
            shipping_method=data['shipping_method'],
            track_number='',
            first_name=data['first_name'],
            last_name=data.get('last_name') or '',
            phone1=data.get('phone1'),
            phone2=data.get('phone2'),
            debt=data.get('debt'),
            balance=data.get('balance') or Decimal('0.00'),
            manual_total=data.get('manual_total'),
            cargo_enabled=False,
            cargo_cost=Decimal('0.00'),
            service_enabled=False,
            service_cost=Decimal('0.00'),
            usd_rate=data.get('usd_rate') or Decimal('12205.00'),
            rmb_rate=data.get('rmb_rate') or Decimal('1807.00'),
            description=data.get('description') or '',
            status=data['status'],
        )

        if order.status == Order.Status.ARRIVED:
            order.come = timezone.now()

        order.save()

        for image in data.get('attachments', []):
            OrderAttachment.objects.create(order=order, image=image)

        return order


class OrderItemForm(forms.Form):
    product_name = forms.CharField(max_length=140, label='Название товара', required=False)
    product_quantity = forms.IntegerField(min_value=1, initial=1, label='Количество', required=False)
    product_price_currency = forms.ChoiceField(choices=Product.Currency.choices, initial=Product.Currency.UZS, label='Валюта', required=False)
    product_price = forms.DecimalField(min_value=0, decimal_places=3, max_digits=18, label='Себестоимость', required=False)
    shipping_method = forms.ChoiceField(
        choices=Order.ShippingMethod.choices,
        initial=Order.ShippingMethod.AVIA,
        label='Тип доставки',
        required=False,
    )
    track_number = forms.CharField(max_length=100, label='Трек-номер товара', required=False)
    store = forms.ChoiceField(choices=Product.Store.choices, initial=Product.Store.NO, label='Магазин', required=False)
    link = forms.URLField(required=False, max_length=1500, label='Ссылка')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product_name'].widget.attrs.update({'placeholder': 'Например: Кроссовки'})
        self.fields['product_quantity'].widget.attrs.update({'min': 1})
        self.fields['product_price'].widget.attrs.update({'step': '0.001', 'placeholder': '0.000'})
        self.fields['track_number'].widget.attrs.update({'placeholder': 'Например: TRK-123456'})
        self.fields['link'].widget.attrs.update({'placeholder': 'https://...'})


class BaseOrderItemFormSet(BaseFormSet):
    def clean(self):
        if any(self.errors):
            return

        active_count = 0

        for form in self.forms:
            cleaned = form.cleaned_data
            if not cleaned:
                continue

            if cleaned.get('DELETE'):
                continue

            name = (cleaned.get('product_name') or '').strip()
            qty = cleaned.get('product_quantity')
            price = cleaned.get('product_price')
            currency = cleaned.get('product_price_currency')
            shipping_method = cleaned.get('shipping_method')
            track_number = (cleaned.get('track_number') or '').strip()
            store = cleaned.get('store')
            link = (cleaned.get('link') or '').strip()

            # entirely empty row is ignored
            if (
                not name
                and price in (None, '')
                and not link
                and qty in (None, 1)
                and shipping_method in (None, '', Order.ShippingMethod.AVIA)
                and not track_number
                and store in (None, '', Product.Store.NO)
            ):
                continue

            if not name:
                form.add_error('product_name', 'Укажите название товара.')
            if not qty:
                form.add_error('product_quantity', 'Укажите количество.')
            if price is None:
                form.add_error('product_price', 'Укажите себестоимость.')
            if not currency:
                form.add_error('product_price_currency', 'Укажите валюту.')
            if not shipping_method:
                cleaned['shipping_method'] = Order.ShippingMethod.AVIA
            if not store:
                form.add_error('store', 'Укажите магазин.')

            if form.errors:
                continue

            active_count += 1

        if active_count == 0:
            raise forms.ValidationError('Добавьте хотя бы один товар в заказ.')


OrderItemFormSet = formset_factory(
    OrderItemForm,
    formset=BaseOrderItemFormSet,
    extra=1,
    can_delete=True,
)


def resolve_manual_total_value(order_form, item_formset):
    payload = {
        'usd_rate': order_form.cleaned_data.get('usd_rate'),
        'rmb_rate': order_form.cleaned_data.get('rmb_rate'),
        'items': [],
    }

    for item_form in item_formset.forms:
        cleaned = item_form.cleaned_data
        if not cleaned or cleaned.get('DELETE'):
            continue

        product_name = (cleaned.get('product_name') or '').strip()
        quantity = cleaned.get('product_quantity')
        price = cleaned.get('product_price')
        currency = cleaned.get('product_price_currency')
        if not product_name or quantity in (None, '') or price is None or not currency:
            continue

        payload['items'].append(
            {
                'quantity': quantity,
                'price': price,
                'currency': currency,
                'store': cleaned.get('store') or '',
                'delete': False,
            }
        )

    totals = _calculate_order_totals_payload(payload)
    manual_total = order_form.cleaned_data.get('manual_total')
    if manual_total is None:
        return None

    if abs(Decimal(manual_total) - totals['auto_total']) < Decimal('0.01'):
        return None
    return manual_total


def save_order_items(order, item_formset):
    primary_shipping_method = None

    for form in item_formset.forms:
        cleaned = form.cleaned_data
        if not cleaned or cleaned.get('DELETE'):
            continue

        product_name = (cleaned.get('product_name') or '').strip()
        if not product_name:
            continue

        shipping_method = cleaned.get('shipping_method') or order.shipping_method or Order.ShippingMethod.AVIA
        track_number = ''.join((cleaned.get('track_number') or '').strip().upper().split())
        if primary_shipping_method is None:
            primary_shipping_method = shipping_method

        OrderItem.objects.create(
            order=order,
            product_name=product_name,
            product_quantity=cleaned['product_quantity'],
            product_price_currency=cleaned['product_price_currency'],
            product_price=cleaned['product_price'],
            shipping_method=shipping_method,
            track_number=track_number,
            store=cleaned['store'],
            link=cleaned.get('link') or None,
        )

    if primary_shipping_method and order.shipping_method != primary_shipping_method:
        order.shipping_method = primary_shipping_method
        order.save(update_fields=['shipping_method', 'updated_at'])


class ChangeOrderForm(forms.ModelForm):
    attachments = MultiFileField(required=False, label='Фото заказа (добавить новые)')

    class Meta:
        model = Order
        fields = [
            'receipt_number',
            'order_date',
            'first_name',
            'last_name',
            'phone1',
            'phone2',
            'debt',
            'balance',
            'manual_total',
            'usd_rate',
            'rmb_rate',
            'description',
            'status',
        ]
        widgets = {
            'order_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['phone1'].widget.attrs.update({'placeholder': '+998 XX XXX XX XX'})
        self.fields['phone2'].widget.attrs.update({'placeholder': 'Доп. номер (опционально)'})
        self.fields['debt'].widget.attrs.update({'step': '0.01'})
        self.fields['balance'].widget.attrs.update({'step': '0.01'})
        self.fields['manual_total'].widget.attrs.update({'step': '0.01'})
        self.fields['usd_rate'].widget.attrs.update(
            {
                'step': '0.01',
                'placeholder': 'Например: 12205',
                'data-exchange-rate': 'usd',
            }
        )
        self.fields['rmb_rate'].widget.attrs.update(
            {
                'step': '0.01',
                'placeholder': 'Например: 1807',
                'data-exchange-rate': 'rmb',
            }
        )
        self.fields['manual_total'].label = 'Итоговая сумма'
        self.fields['description'].widget.attrs.update({'placeholder': 'Комментарий к заказу'})
        self.fields['attachments'].widget.attrs.update(
            {
                'class': 'upload-input',
                'aria-describedby': 'attachments-edit-hint attachments-edit-meta',
            }
        )

    def clean(self):
        cleaned_data = super().clean()
        balance = cleaned_data.get('balance') or Decimal('0.00')

        cleaned_data['balance'] = balance

        return cleaned_data
