from decimal import Decimal

from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from .utils import get_random_symbols


class Product(models.Model):
    # Legacy model: сохраняем для обратной совместимости со старыми записями.
    class Currency(models.TextChoices):
        USD = 'USD', 'USD'
        UZS = 'UZS', 'UZS'
        RMB = 'RMB', 'RMB'

    class Store(models.TextChoices):
        NO = 'None', 'None'
        TAOBAO = 'Taobao', 'Taobao'
        ALIBABA = 'Alibaba', 'Alibaba'
        ALIEXPRESS = 'AliExpress', 'AliExpress'
        PINDUODUO = 'Pinduoduo', 'Pinduoduo'
        POIZON = 'Poizon', 'Poizon'
        SIX = '1688', '1688'
        NINETY_FIVE = '95', '95'
        MADE_IN_CHINA = 'MadeChina', 'Made in China'

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='Admin')
    product_name = models.CharField(max_length=100, verbose_name='Mahsulot Nomi', db_index=True)
    product_quantity = models.PositiveIntegerField(default=1, verbose_name='Mahsulot Soni')
    product_price_currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        default=Currency.UZS,
        verbose_name='Mahsulot Valyutasi',
    )
    product_price = models.DecimalField(
        validators=[MinValueValidator(0.0)],
        max_digits=18,
        decimal_places=3,
        default='0.1',
        verbose_name='Mahsulot Narxi',
    )
    store = models.CharField(max_length=10, choices=Store.choices, default='None', verbose_name='Mahsulot Do`koni')
    link = models.URLField(max_length=1500, null=True, blank=True, verbose_name='Mahsulot Linki')
    image1 = models.ImageField(upload_to='products/images/', default='product.png', verbose_name='Mahsulot Rasmi #1')
    image2 = models.ImageField(upload_to='products/images/', default='product.png', verbose_name='Mahsulot Rasmi #2')
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True, verbose_name='Yaratilgan Sana')
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True, verbose_name='O`zgartirilgan Sana')

    def __str__(self):
        return f"{self.product_name} | {self.store}"

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'


class ProductDetail(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    kgs = models.DecimalField(max_digits=5, decimal_places=3, default=0.500, verbose_name='Og`irlig')
    cargo = models.DecimalField(max_digits=7, decimal_places=3, default=9, verbose_name='Cargo')
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True, verbose_name='Yaratilgan Sana')
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True, verbose_name='O`zgartirilgan Sana')

    def __str__(self):
        return f"{self.product.product_name} | KG {self.kgs} | ${self.cargo}"

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = 'Деталь товара'
        verbose_name_plural = 'Детали товаров'


class Order(models.Model):
    class Status(models.TextChoices):
        ACCEPTED = 'accepted', 'Принят'
        ORDERED = 'ordered', 'Заказан'
        TRANSIT = 'transit', 'В пути'
        ARRIVED = 'arrived', 'Прибыл'
        CANCELLED = 'cancelled', 'Отмена'

    class ShippingMethod(models.TextChoices):
        AVIA = 'AVIA', 'АВИА'
        IPOST = 'iPost', 'iPost'
        CARGO_17994 = '17994', '17994'

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    # Legacy link for old orders. New orders store items in OrderItem.
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    slug = models.SlugField(unique=True, blank=True, null=True)
    receipt_number = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name='Kvitansiya Raqam',
        db_index=True,
    )
    order_date = models.DateField(default=timezone.now, verbose_name='Sana', db_index=True)
    shipping_method = models.CharField(
        max_length=8,
        choices=ShippingMethod.choices,
        default=ShippingMethod.AVIA,
        verbose_name='Yuborish turi',
    )
    track_number = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    first_name = models.CharField(max_length=100, verbose_name='Mijoz Ismi', db_index=True)
    last_name = models.CharField(max_length=100, verbose_name='Mijoz Familiyasi', blank=True, db_index=True)
    phone1 = models.PositiveBigIntegerField(
        verbose_name='Raqam #1',
        blank=True,
        null=True,
        default=999999999,
        db_index=True,
    )
    phone2 = models.PositiveBigIntegerField(verbose_name='Raqam #2', blank=True, null=True, default=None, db_index=True)
    debt = models.DecimalField(
        validators=[MinValueValidator(0.0)],
        decimal_places=2,
        max_digits=17,
        verbose_name='Qarz',
        blank=True,
        null=True,
    )
    balance = models.DecimalField(
        validators=[MinValueValidator(0.0)],
        decimal_places=2,
        max_digits=17,
        default=0,
        blank=True,
        null=True,
        verbose_name='Баланс',
    )
    cargo_cost = models.DecimalField(
        validators=[MinValueValidator(0.0)],
        decimal_places=2,
        max_digits=17,
        default=0,
        blank=True,
        null=True,
        verbose_name='Cargo',
    )
    cargo_enabled = models.BooleanField(default=True, verbose_name='Cargo yoqilgan')
    service_cost = models.DecimalField(
        validators=[MinValueValidator(0.0)],
        decimal_places=2,
        max_digits=17,
        default=0,
        blank=True,
        null=True,
        verbose_name='Xizmat',
    )
    manual_total = models.DecimalField(
        validators=[MinValueValidator(0.0)],
        decimal_places=2,
        max_digits=17,
        blank=True,
        null=True,
        verbose_name='Итог вручную',
    )
    service_enabled = models.BooleanField(default=True, verbose_name='Xizmat yoqilgan')
    usd_rate = models.DecimalField(
        validators=[MinValueValidator(0.0)],
        decimal_places=2,
        max_digits=17,
        default=12205,
        verbose_name='USD kursi',
    )
    rmb_rate = models.DecimalField(
        validators=[MinValueValidator(0.0)],
        decimal_places=2,
        max_digits=17,
        default=1807,
        verbose_name='RMB kursi',
    )
    description = models.TextField(max_length=500, verbose_name='Tarif', default='', blank=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.ACCEPTED,
        verbose_name='Status',
        db_index=True,
    )
    come = models.DateTimeField(default=timezone.now, blank=True, null=True, verbose_name='Kelgan Sana', db_index=True)

    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True, verbose_name='Yaratilgan Sana', db_index=True)
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True, verbose_name='O`zgartirilgan Sana')

    class Meta:
        ordering = ['-order_date', '-created_at', '-id']
        indexes = [
            models.Index(fields=['status', 'order_date'], name='order_status_date_idx'),
            models.Index(fields=['user', 'order_date'], name='order_user_date_idx'),
            models.Index(fields=['order_date', 'created_at'], name='order_date_created_idx'),
            models.Index(fields=['status', 'come'], name='order_status_come_idx'),
        ]
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'

    def save(self, *args, **kwargs):
        if not self.slug:
            base_name = self.first_name or 'order'
            if self.product:
                base_name = self.product.product_name
            self.slug = slugify(base_name + get_random_symbols())
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.receipt_number} {self.last_name} {self.first_name}"

    def _items_cache(self):
        if not hasattr(self, '_cached_items'):
            self._cached_items = list(self.items.all())
        return self._cached_items

    def convert_to_uzs(self, amount, currency):
        amount_decimal = Decimal(amount or '0.00')
        currency_code = (currency or Product.Currency.UZS).upper()
        if currency_code == Product.Currency.USD:
            return amount_decimal * Decimal(self.usd_rate or '0.00')
        if currency_code == Product.Currency.RMB:
            return amount_decimal * Decimal(self.rmb_rate or '0.00')
        return amount_decimal

    @property
    def has_items(self):
        return len(self._items_cache()) > 0

    @property
    def get_display_product_name(self):
        items = self._items_cache()
        if items:
            first_name = items[0].product_name
            if len(items) == 1:
                return first_name
            return f"{first_name} +{len(items) - 1}"

        if self.product:
            return self.product.product_name
        return '-'

    @property
    def get_total_price(self):
        items = self._items_cache()
        if items:
            return sum(
                (self.convert_to_uzs(item.get_subtotal, item.product_price_currency) for item in items),
                Decimal('0.00'),
            )

        if not self.product:
            return Decimal('0.00')
        return self.convert_to_uzs(
            Decimal(self.product.product_quantity) * self.product.product_price,
            self.product.product_price_currency,
        )

    @property
    def is_aliexpress_only(self):
        items = self._items_cache()
        if items:
            return all(item.store == Product.Store.ALIEXPRESS for item in items)

        if self.product:
            return self.product.store == Product.Store.ALIEXPRESS
        return False

    @property
    def get_extra_cost(self):
        return Decimal('0.00')

    @property
    def get_final_total(self):
        if self.manual_total is not None:
            return Decimal(self.manual_total)
        return self.get_total_price

    @property
    def get_pickup_due(self):
        debt = self.debt or Decimal('0.00')
        return debt

    @property
    def get_balance(self):
        return self.balance or Decimal('0.00')

    @property
    def get_current(self):
        return Product.Currency.UZS

    @property
    def pricing_note(self):
        return 'Итог рассчитывается по сумме товаров (в UZS по курсу заказа).'

    @staticmethod
    def shipping_method_label(method_code):
        return dict(Order.ShippingMethod.choices).get(method_code, method_code or '-')

    @property
    def shipping_methods_codes(self):
        items = self._items_cache()
        if items:
            methods = []
            for item in items:
                code = item.shipping_method or self.shipping_method
                if code and code not in methods:
                    methods.append(code)
            return methods
        if self.shipping_method:
            return [self.shipping_method]
        return []

    @property
    def shipping_methods_display(self):
        return [self.shipping_method_label(code) for code in self.shipping_methods_codes]

    @property
    def shipping_method_summary(self):
        methods = self.shipping_methods_display
        if not methods:
            return '-'
        return ' / '.join(methods)

    @property
    def primary_shipping_method(self):
        methods = self.shipping_methods_codes
        if methods:
            return methods[0]
        return self.shipping_method or Order.ShippingMethod.AVIA

    @property
    def item_track_numbers(self):
        tracks = []
        for item in self._items_cache():
            track = (item.track_number or '').strip()
            if track and track not in tracks:
                tracks.append(track)
        if tracks:
            return tracks
        legacy_track = (self.track_number or '').strip()
        return [legacy_track] if legacy_track else []

    @property
    def item_track_summary(self):
        tracks = self.item_track_numbers
        if not tracks:
            return '-'
        if len(tracks) == 1:
            return tracks[0]
        return f'{tracks[0]} +{len(tracks) - 1}'


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product_name = models.CharField(max_length=140, verbose_name='Название товара', db_index=True)
    product_quantity = models.PositiveIntegerField(default=1, verbose_name='Количество')
    product_price_currency = models.CharField(max_length=3, choices=Product.Currency.choices, default=Product.Currency.UZS)
    product_price = models.DecimalField(max_digits=18, decimal_places=3, validators=[MinValueValidator(0.0)])
    shipping_method = models.CharField(
        max_length=8,
        choices=Order.ShippingMethod.choices,
        default=Order.ShippingMethod.AVIA,
        verbose_name='Тип доставки',
    )
    track_number = models.CharField(max_length=100, blank=True, null=True, db_index=True, verbose_name='Трек-номер')
    store = models.CharField(max_length=10, choices=Product.Store.choices, default=Product.Store.NO)
    link = models.URLField(max_length=1500, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['id']
        verbose_name = 'Товар в заказе'
        verbose_name_plural = 'Товары в заказе'

    def __str__(self):
        return f'{self.product_name} x{self.product_quantity}'

    @property
    def get_subtotal(self):
        return Decimal(self.product_quantity) * self.product_price


class OrderAttachment(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='attachments')
    image = models.ImageField(upload_to='orders/images/')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']
        verbose_name = 'Вложение заказа'
        verbose_name_plural = 'Вложения заказов'

    def __str__(self):
        return f'Attachment #{self.id} for order {self.order_id}'


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(upload_to='users/avatars/', blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['user_id']
        verbose_name = 'Профиль пользователя'
        verbose_name_plural = 'Профили пользователей'

    def __str__(self):
        return f'Profile for @{self.user.username}'
