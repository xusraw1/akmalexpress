from decimal import Decimal

from django import forms
from django.forms import BaseFormSet, formset_factory
from django.utils import timezone

from .models import Order, OrderAttachment, OrderItem, Product


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

    debt = forms.DecimalField(min_value=0, required=False, decimal_places=2, max_digits=7, label='Долг')
    shipping_method = forms.ChoiceField(
        choices=Order.ShippingMethod.choices,
        initial=Order.ShippingMethod.AVIA,
        label='Тип отправки',
    )
    status = forms.ChoiceField(choices=Order.Status.choices, initial=Order.Status.ACCEPTED, label='Статус')

    track_pending = forms.BooleanField(required=False, initial=True, label='Трек-номер пока не получен')
    track_number = forms.CharField(max_length=100, required=False, label='Трек-номер')

    cargo_enabled = forms.BooleanField(required=False, initial=True, label='Добавить карго (можно позже)')
    cargo_cost = forms.DecimalField(min_value=0, required=False, decimal_places=2, max_digits=10, initial=0, label='Карго')
    service_enabled = forms.BooleanField(required=False, initial=True, label='Добавить услугу (можно позже)')
    service_cost = forms.DecimalField(min_value=0, required=False, decimal_places=2, max_digits=10, initial=0, label='Услуга')
    usd_rate = forms.DecimalField(min_value=0.01, required=True, decimal_places=2, max_digits=12, initial=12205, label='Курс USD')
    rmb_rate = forms.DecimalField(min_value=0.01, required=True, decimal_places=2, max_digits=12, initial=1807, label='Курс RMB')
    description = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3}), label='Комментарий')

    attachments = MultiFileField(required=False, label='Фото заказа (можно несколько)')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['track_number'].help_text = 'Если трек еще не выдали, оставьте галочку выше.'
        self.fields['receipt_number'].widget.attrs.update({'placeholder': 'Например: 245'})
        self.fields['first_name'].widget.attrs.update({'placeholder': 'Имя клиента'})
        self.fields['last_name'].widget.attrs.update({'placeholder': 'Фамилия клиента'})
        self.fields['phone1'].widget.attrs.update({'placeholder': '+998 XX XXX XX XX'})
        self.fields['phone2'].widget.attrs.update({'placeholder': 'Доп. номер (опционально)'})
        self.fields['track_number'].widget.attrs.update({'placeholder': 'Оставьте пустым, если трека пока нет'})
        self.fields['cargo_cost'].widget.attrs.update({'step': '0.01'})
        self.fields['service_cost'].widget.attrs.update({'step': '0.01'})
        self.fields['usd_rate'].widget.attrs.update({'step': '0.01', 'placeholder': 'Например: 12205'})
        self.fields['rmb_rate'].widget.attrs.update({'step': '0.01', 'placeholder': 'Например: 1807'})
        self.fields['debt'].widget.attrs.update({'step': '0.01'})
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

        track_pending = cleaned_data.get('track_pending')
        track_number = (cleaned_data.get('track_number') or '').strip()

        if track_pending:
            cleaned_data['track_number'] = ''
        elif not track_number:
            self.add_error('track_number', 'Введите трек-номер или отметьте, что трек пока не получен.')

        cargo_enabled = bool(cleaned_data.get('cargo_enabled'))
        service_enabled = bool(cleaned_data.get('service_enabled'))
        cleaned_data['cargo_enabled'] = cargo_enabled
        cleaned_data['service_enabled'] = service_enabled

        cargo_cost = cleaned_data.get('cargo_cost') or Decimal('0.00')
        service_cost = cleaned_data.get('service_cost') or Decimal('0.00')

        if not cargo_enabled:
            cargo_cost = Decimal('0.00')
        if not service_enabled:
            service_cost = Decimal('0.00')

        cleaned_data['cargo_cost'] = cargo_cost
        cleaned_data['service_cost'] = service_cost

        return cleaned_data

    def save_order(self, user):
        data = self.cleaned_data
        order = Order(
            user=user,
            receipt_number=data['receipt_number'],
            order_date=data['order_date'],
            shipping_method=data['shipping_method'],
            track_number=data.get('track_number') or '',
            first_name=data['first_name'],
            last_name=data.get('last_name') or '',
            phone1=data.get('phone1'),
            phone2=data.get('phone2'),
            debt=data.get('debt'),
            cargo_enabled=data.get('cargo_enabled', True),
            cargo_cost=data.get('cargo_cost') or Decimal('0.00'),
            service_enabled=data.get('service_enabled', True),
            service_cost=data.get('service_cost') or Decimal('0.00'),
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
    product_price = forms.DecimalField(min_value=0, decimal_places=3, max_digits=10, label='Себестоимость', required=False)
    store = forms.ChoiceField(choices=Product.Store.choices, initial=Product.Store.NO, label='Магазин', required=False)
    link = forms.URLField(required=False, max_length=1500, label='Ссылка')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['product_name'].widget.attrs.update({'placeholder': 'Например: Кроссовки'})
        self.fields['product_quantity'].widget.attrs.update({'min': 1})
        self.fields['product_price'].widget.attrs.update({'step': '0.001', 'placeholder': '0.000'})
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
            store = cleaned.get('store')
            link = (cleaned.get('link') or '').strip()

            # entirely empty row is ignored
            if (
                not name
                and price in (None, '')
                and not link
                and qty in (None, 1)
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


def save_order_items(order, item_formset):
    for form in item_formset.forms:
        cleaned = form.cleaned_data
        if not cleaned or cleaned.get('DELETE'):
            continue

        product_name = (cleaned.get('product_name') or '').strip()
        if not product_name:
            continue

        OrderItem.objects.create(
            order=order,
            product_name=product_name,
            product_quantity=cleaned['product_quantity'],
            product_price_currency=cleaned['product_price_currency'],
            product_price=cleaned['product_price'],
            store=cleaned['store'],
            link=cleaned.get('link') or None,
        )


class ChangeOrderForm(forms.ModelForm):
    track_pending = forms.BooleanField(
        required=False,
        initial=False,
        label='Трек-номер пока не получен',
    )

    class Meta:
        model = Order
        fields = [
            'receipt_number',
            'order_date',
            'shipping_method',
            'track_number',
            'first_name',
            'last_name',
            'phone1',
            'phone2',
            'debt',
            'cargo_enabled',
            'cargo_cost',
            'service_enabled',
            'service_cost',
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
        instance = kwargs.get('instance')
        self.fields['track_number'].required = False
        self.fields['track_number'].help_text = 'Если трек еще не выдали, оставьте галочку выше.'
        self.fields['phone1'].widget.attrs.update({'placeholder': '+998 XX XXX XX XX'})
        self.fields['phone2'].widget.attrs.update({'placeholder': 'Доп. номер (опционально)'})
        self.fields['track_number'].widget.attrs.update({'placeholder': 'Оставьте пустым, если трека пока нет'})
        self.fields['debt'].widget.attrs.update({'step': '0.01'})
        self.fields['cargo_cost'].widget.attrs.update({'step': '0.01'})
        self.fields['service_cost'].widget.attrs.update({'step': '0.01'})
        self.fields['usd_rate'].widget.attrs.update({'step': '0.01', 'placeholder': 'Например: 12205'})
        self.fields['rmb_rate'].widget.attrs.update({'step': '0.01', 'placeholder': 'Например: 1807'})
        self.fields['cargo_enabled'].label = 'Добавить карго (можно позже)'
        self.fields['service_enabled'].label = 'Добавить услугу (можно позже)'
        self.fields['description'].widget.attrs.update({'placeholder': 'Комментарий к заказу'})
        if instance is not None:
            self.fields['track_pending'].initial = not bool(instance.track_number)

    def clean(self):
        cleaned_data = super().clean()
        track_pending = cleaned_data.get('track_pending')
        track_number = (cleaned_data.get('track_number') or '').strip()

        if track_pending:
            cleaned_data['track_number'] = ''
        elif not track_number:
            self.add_error('track_number', 'Введите трек-номер или отметьте, что трек пока не получен.')

        cargo_enabled = bool(cleaned_data.get('cargo_enabled'))
        service_enabled = bool(cleaned_data.get('service_enabled'))
        cleaned_data['cargo_enabled'] = cargo_enabled
        cleaned_data['service_enabled'] = service_enabled

        cargo_cost = cleaned_data.get('cargo_cost') or Decimal('0.00')
        service_cost = cleaned_data.get('service_cost') or Decimal('0.00')

        if not cargo_enabled:
            cargo_cost = Decimal('0.00')
        if not service_enabled:
            service_cost = Decimal('0.00')

        cleaned_data['cargo_cost'] = cargo_cost
        cleaned_data['service_cost'] = service_cost

        return cleaned_data
