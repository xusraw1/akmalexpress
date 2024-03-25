from django.shortcuts import render, redirect, get_object_or_404
from .forms import CreateProductForm, CreateOrderForm, ChangeOrderForm
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from .models import Product, Order
from django.db.models import Q
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger


def index(request):
    if request.GET.get('search'):
        search = request.GET.get('search')
        orders = Order.objects.filter(Q(receipt_number__icontains=search) |
                                      Q(track_number__icontains=search) |
                                      Q(first_name__icontains=search) |
                                      Q(last_name__icontains=search) |
                                      Q(product__product_name__icontains=search))

        if orders:
            messages.success(request, f"Заказы по вашему запросу '{search}' найдены")
            return render(request, 'index.html', {'orders': orders})
        messages.info(request, f"По вашему запросу '{search}' ничего не найдено")

    return render(request, 'index.html')


def change_order(request, slug):
    orderr = get_object_or_404(Order, slug=slug)
    form = ChangeOrderForm(instance=orderr)

    if request.method == 'POST':
        form = ChangeOrderForm(request.POST, instance=orderr)

        if form.is_valid():
            order = form.save(commit=False)

            if order.status == 'end':
                order.come = timezone.now()
            else:
                order.come = None

            order.save()
            messages.success(request, f"Заказ с квитанцией №{order.receipt_number} обновлен")
            return redirect('orders')

        messages.warning(request, 'Введенные данные неверны')
        return render(request, 'akmalexpress/change_order.html', {'form': form, 'orderr': orderr})

    return render(request, 'akmalexpress/change_order.html', {'form': form, 'orderr': orderr})


def create_order(request):
    last_order = Order.objects.last().receipt_number
    form = CreateOrderForm()
    if request.method == 'POST':
        form = CreateOrderForm(request.POST)
        product = Product.objects.last()
        if form.is_valid():
            order = form.save(commit=False)
            order.product = product
            order.user = request.user
            order.save()
            messages.success(request, 'Заказ успешно создан')
            return redirect('/')
        messages.warning(request, 'Форма заполнено неправильно')
        return render(request, 'akmalexpress/create_order.html', {'form': form, 'last_order': last_order})
    return render(request, 'akmalexpress/create_order.html', {'form': form, 'last_order': last_order})


def create_product(request):
    form = CreateProductForm()
    context = {'form': form}
    if request.method == 'POST':
        form = CreateProductForm(data=request.POST, files=request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.username = request.user
            product.save()
            messages.success(request, "Продукт добавлен")
            return redirect('create_order')
        messages.error(request, "Форма заполнена неверно")
        return render(request, 'akmalexpress/create_product.html', context)
    return render(request, 'akmalexpress/create_product.html', context)


def order_list(request):
    orders_list = Order.objects.all().order_by('-created_at')

    paginator = Paginator(orders_list, 10)

    page_number = request.GET.get('page')

    try:
        orders = paginator.page(page_number)
    except PageNotAnInteger:
        orders = paginator.page(1)
    except EmptyPage:
        orders = paginator.page(paginator.num_pages)

    context = {'orders': orders}
    return render(request, 'akmalexpress/orders.html', context)


def profile_view(request, user):
    profile = User.objects.get(username=user)
    orders = Order.objects.filter(user=profile)

    paginator = Paginator(orders, 10)

    page_number = request.GET.get('page')

    try:
        orders = paginator.page(page_number)
    except PageNotAnInteger:
        orders = paginator.page(1)
    except EmptyPage:
        orders = paginator.page(paginator.num_pages)
    return render(request, 'akmalexpress/profile.html', {'profile': profile, 'orders': orders})


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, 'Вы вошли в свой аккаунт')
            return redirect('/')
        messages.error(request, 'Пользователь не найден, попробуйте заново')
        return redirect('login')
    return render(request, 'akmalexpress/login.html')


def logout_view(request):
    logout(request)
    messages.warning(request, "Вы вышли из аккаунта")
    return redirect('login')
