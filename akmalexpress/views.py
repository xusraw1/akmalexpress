from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponseNotAllowed
from django.shortcuts import render, redirect, get_object_or_404
from .forms import CreateProductForm, CreateOrderForm, ChangeOrderForm
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from .models import Product, Order
from django.db.models import Q
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth.decorators import user_passes_test


def active_superuser_required(view_func):
    def _wrapped_view(request, *args, **kwargs):
        if not (request.user.is_active or request.user.is_superuser):
            messages.error(request, "У вас нет прав для доступа к этой странице")
            return redirect('/login/')
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def superuser_required(view_func):
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, "У вас нет прав для доступа к этой странице")
            return redirect('/')
        return view_func(request, *args, **kwargs)

    return _wrapped_view


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


def detail_order(request, slug):
    order = get_object_or_404(Order, slug=slug)
    return render(request, 'akmalexpress/detail_order.html', {'order': order})


@active_superuser_required
def delete_order(request, slug):
    order = get_object_or_404(Order, slug=slug)
    if request.method == 'POST':
        order.delete()
        messages.success(request, f"Заказ с номером №{order.receipt_number} успешно удалено")
        return redirect('/')
    return render(request, 'akmalexpress/delete_order.html', {'order': order})


@active_superuser_required
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


@active_superuser_required
def create_order(request):
    last_order = Order.objects.last()
    receipt_number = None
    if last_order is not None:
        receipt_number = last_order.receipt_number
    else:
        pass
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
        return render(request, 'akmalexpress/create_order.html', {'form': form, 'receipt_number': receipt_number})
    return render(request, 'akmalexpress/create_order.html', {'form': form, 'receipt_number': receipt_number})


@active_superuser_required
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


@active_superuser_required
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


@active_superuser_required
def profile_view(request, user):
    try:
        profile = User.objects.get(username=user)
    except ObjectDoesNotExist:
        messages.error(request, 'Пользователь не найден')
        return redirect('index')

    if not (profile.is_superuser or profile.is_staff or profile.is_active):
        messages.warning(request, 'Вы не имеете доступ к этому профилю')
        return redirect('index')

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
    if request.user.is_authenticated:
        messages.error(request, "Для того чтобы войти в другую учетную запись, вы должны завершить текущий сеанс")
        return redirect('/')
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        print(username)
        print(password)
        user = authenticate(request, username=username, password=password)
        print(user)
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


@superuser_required
def toggle_status(request, user_id):
    if request.method == 'POST':
        user = User.objects.get(id=user_id)
        action = request.POST.get('action')
        if action == 'activate':
            user.is_active = True
            user.is_staff = True
            user.save()
            messages.success(request, f"Модератор {user} активирован")
        elif action == 'deactivate':
            user.is_active = False
            user.is_staff = False
            user.save()
            messages.info(request, f"Модератор {user} деактивирован")
            if not user.is_superuser:
                return redirect('create_admin')
            else:
                return redirect('/')
        return redirect('create_admin')
    else:
        return HttpResponseNotAllowed(['POST'])


@superuser_required
def create_admin(request):
    users = User.objects.exclude(is_superuser=True)
    if request.method == 'POST':
        username = request.POST.get('username')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        user = User.objects.filter(username=username)
        if not user:
            if username and password1 == password2:
                user = User.objects.create_user(username=username, password=password1)
                user.save()
                messages.success(request, "Успешно добавлен")
                return redirect('create_admin')
            else:
                messages.warning(request, "Пароли не совпадают или не указано имя пользователя")
                return redirect('create_admin')
        messages.warning(request, f"Пользователь с ником {username} уже существует!")
        return redirect('create_admin')
    return render(request, 'akmalexpress/create_admin.html', {'users': users})
