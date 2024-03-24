from django.shortcuts import render, redirect
from .forms import CreateProductForm, CreateOrderForm
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from .models import Product, Order


def index(request):
    return render(request, 'index.html')


def create_order(request):
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
        return render(request, 'akmalexpress/create_order.html', {'form': form})
    return render(request, 'akmalexpress/create_order.html', {'form': form})


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
    orders = Order.objects.all().order_by('-created_at')
    context = {'orders': orders}
    return render(request, 'akmalexpress/orders.html', context)


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
