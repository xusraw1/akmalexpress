from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.utils.text import slugify
from .utils import get_random_symbols


class Product(models.Model):
    class Currency(models.TextChoices):
        USD = 'USD', 'USD'
        UZS = 'UZS', 'UZS'
        RMB = 'RMB', 'RMB'

    class Store(models.TextChoices):
        NO = 'None', 'None'
        TAOBAO = 'Taoboa', 'Taobao'
        ALIBABA = 'Alibaba', 'Alibaba'
        ALIEXPRESS = 'AliExpress', 'AliExpress'
        PINDUODUO = 'Pinduoduo', 'Pinduoduo'
        SIX = '1688', '1688'

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='Admin')
    product_name = models.CharField(max_length=100, verbose_name='Mahsulot Nomi')
    product_quantity = models.PositiveIntegerField(default=1, verbose_name='Mahsulot Soni')
    product_price_currency = models.CharField(max_length=3, choices=Currency.choices, default=Currency.UZS,
                                              verbose_name='Mahsulot Valyutasi')
    product_price = models.DecimalField(validators=[MinValueValidator(0.0)], max_digits=10, decimal_places=3,
                                        default='0.1', verbose_name='Mahsulot Narxi')
    store = models.CharField(max_length=10, choices=Store.choices, default='None', verbose_name='Mahsulot Do`koni')
    link = models.URLField(max_length=1500, null=True, blank=True, verbose_name='Mahsulot Linki')
    image1 = models.ImageField(upload_to='products/images/', default='product.png', verbose_name='Mahsulot Rasmi #1')
    image2 = models.ImageField(upload_to='products/images/', default='product.png', verbose_name='Mahsulot Rasmi #2')
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True, verbose_name='Yaratilgan Sana')
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True, verbose_name='O`zgartirilgan Sana')

    def __str__(self):
        return f"{self.product_name} | {self.store}"


class ProductDetail(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    kgs = models.DecimalField(max_digits=5, decimal_places=3, default=0.500, verbose_name='Og`irlig')
    cargo = models.DecimalField(max_digits=7, decimal_places=3, default=9, verbose_name='Cargo')
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True, verbose_name='Yaratilgan Sana')
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True, verbose_name='O`zgartirilgan Sana')

    def __str__(self):
        return f"{self.product.product_name} | KG {self.kgs} | ${self.cargo}"


class Order(models.Model):
    class Status(models.TextChoices):
        NO = 'none', 'None'  # BERILMADI

        berildi = 'start', 'Начат'  # ZAKAZ BERILDI
        yolda = 'continue', 'В пути'  # ZAKAZ YO`LDA
        keldi = 'end', 'Пришел'  # ZAKAZ KELDI

        force = 'force', 'Отменен'  # ZAKAZ OTMEN BO`LDI

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    slug = models.SlugField(unique=True, blank=True, null=True)
    receipt_number = models.PositiveIntegerField(validators=[MaxValueValidator(1500)])
    track_number = models.CharField(max_length=50, null=True, blank=True)
    first_name = models.CharField(max_length=100, verbose_name='Mijoz Ismi')
    last_name = models.CharField(max_length=100, verbose_name='Mijoz Familiyasi', blank=True)
    phone1 = models.PositiveIntegerField(verbose_name='Raqam #1', blank=True,
                                         null=True,
                                         default=999999999)
    phone2 = models.PositiveIntegerField(verbose_name='Raqam #2', blank=True,
                                         null=True,
                                         default=999999999)
    debt = models.DecimalField(validators=[MinValueValidator(0.0)], decimal_places=2, max_digits=7, verbose_name='Qarz',
                               blank=True, null=True)
    description = models.TextField(max_length=500, verbose_name='Tarif')
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.NO, verbose_name='Status')
    come = models.DateTimeField(default=timezone.now, blank=True, null=True, verbose_name='Kelgan Sana')

    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True, verbose_name='Yaratilgan Sana')
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True, verbose_name='O`zgartirilgan Sana')

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.product.product_name + get_random_symbols())
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.receipt_number} {self.last_name} {self.first_name}"
