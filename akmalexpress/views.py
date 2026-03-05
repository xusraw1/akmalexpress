from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from functools import wraps

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Q
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone

from .forms import ChangeOrderForm, CreateOrderForm, OrderItemFormSet, save_order_items
from .i18n import normalize_language
from .models import Order


def orders_with_related(queryset):
    return queryset.select_related('product', 'user').prefetch_related('items', 'attachments')


def parse_month_filter(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m")
    except ValueError:
        return None


def configure_order_item_formset(item_formset):
    for form in item_formset.forms:
        if 'DELETE' in form.fields:
            form.fields['DELETE'].widget.attrs.update(
                {
                    'hidden': 'hidden',
                    'tabindex': '-1',
                    'aria-hidden': 'true',
                    'class': 'row-delete-input',
                }
            )
    return item_formset


def is_active_superuser(user):
    return user.is_staff or user.is_superuser


def user_is_order_creator(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        slug = kwargs.get('slug')
        order = Order.objects.filter(slug=slug).first()
        if not order:
            return redirect('/')

        if request.user.is_superuser or request.user.is_staff or request.user == order.user:
            return view_func(request, *args, **kwargs)

        messages.error(request, "У вас нет прав для доступа к этой странице")
        return redirect('/')

    return _wrapped_view


def superuser_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, "У вас нет прав для доступа к этой странице")
            return redirect('/')
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def index(request):
    context = {}
    search = request.GET.get('search')
    if search:
        search_filter = (
            Q(receipt_number__icontains=search)
            | Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(items__product_name__icontains=search)
            | Q(product__product_name__icontains=search)
        )
        if request.user.is_staff or request.user.is_superuser:
            search_filter |= Q(track_number__icontains=search)

        orders = orders_with_related(
            Order.objects.filter(search_filter)
            .distinct()
            .order_by('-order_date', '-created_at')
        )

        if orders.exists():
            messages.success(request, f"Заказы по вашему запросу '{search}' найдены")
            context['orders'] = orders
        else:
            messages.info(request, f"По вашему запросу '{search}' ничего не найдено")

    return render(request, 'index.html', context)


def contacts_view(request):
    return render(request, 'akmalexpress/contacts.html')


def set_language_view(request, lang_code):
    language = normalize_language(lang_code)
    request.session['site_language'] = language

    next_url = request.GET.get('next') or request.META.get('HTTP_REFERER') or '/'
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        next_url = '/'

    response = redirect(next_url)
    response.set_cookie('site_language', language, max_age=60 * 60 * 24 * 365)
    return response


def detail_order(request, slug):
    order = get_object_or_404(orders_with_related(Order.objects.all()), slug=slug)
    if request.user.is_staff or request.user.is_superuser:
        return render(request, 'akmalexpress/detail_order.html', {'order': order})
    return render(request, 'akmalexpress/client_order_detail.html', {'order': order})


@user_passes_test(is_active_superuser)
def print_receipt(request, slug):
    order = get_object_or_404(orders_with_related(Order.objects.all()), slug=slug)
    return render(request, 'akmalexpress/receipt_print.html', {'order': order})


@user_passes_test(is_active_superuser)
@user_is_order_creator
def delete_order(request, slug):
    order = get_object_or_404(Order, slug=slug)
    if request.method == 'POST':
        order.delete()
        messages.success(request, f"Заказ с номером №{order.receipt_number} успешно удален")
        return redirect('/')
    return render(request, 'akmalexpress/delete_order.html', {'order': order})


@user_passes_test(is_active_superuser)
@user_is_order_creator
def change_order(request, slug):
    orderr = get_object_or_404(Order, slug=slug)
    form = ChangeOrderForm(instance=orderr)

    if request.method == 'POST':
        form = ChangeOrderForm(request.POST, instance=orderr)

        if form.is_valid():
            order = form.save(commit=False)
            if order.status == Order.Status.keldi:
                order.come = timezone.now()
            elif order.status != Order.Status.keldi:
                order.come = None

            order.save()
            messages.success(request, f"Заказ с квитанцией №{order.receipt_number} обновлен")
            return redirect('orders')

        messages.warning(request, 'Введенные данные неверны')

    return render(request, 'akmalexpress/change_order.html', {'form': form, 'orderr': orderr})


@user_passes_test(is_active_superuser)
def create_order(request):
    last_order = Order.objects.order_by('-receipt_number').first()
    previous_receipt_number = last_order.receipt_number if last_order is not None else None
    next_receipt_number = (last_order.receipt_number + 1) if last_order is not None else 1

    form = CreateOrderForm(initial={'receipt_number': next_receipt_number})
    item_formset = configure_order_item_formset(OrderItemFormSet(prefix='items'))

    if request.method == 'POST':
        form = CreateOrderForm(request.POST, request.FILES)
        item_formset = configure_order_item_formset(OrderItemFormSet(request.POST, prefix='items'))

        if form.is_valid() and item_formset.is_valid():
            order = form.save_order(user=request.user)
            save_order_items(order, item_formset)

            messages.success(request, f'Заказ №{order.receipt_number} успешно создан')

            if not order.track_number:
                remind_at = order.order_date + timedelta(days=2)
                messages.warning(
                    request,
                    f"Трек-номер пока не добавлен. Проверьте заказ и добавьте трек до {remind_at.strftime('%d.%m.%Y')}.",
                )

            return redirect('orders')

        messages.warning(request, 'Проверьте форму: есть ошибки в данных заказа или товаров.')

    return render(
        request,
        'akmalexpress/create_order.html',
        {
            'form': form,
            'item_formset': item_formset,
            'receipt_number': previous_receipt_number,
            'next_receipt_number': next_receipt_number,
        },
    )


@user_passes_test(is_active_superuser)
def create_product(request):
    messages.info(request, 'Создание товара перенесено в единую форму создания заказа.')
    return redirect('create_order')


@user_passes_test(is_active_superuser)
def order_list(request):
    orders_list = Order.objects.all().order_by('-order_date', '-created_at')

    selected_month = request.GET.get('month', '').strip()
    month_date = None
    if request.user.is_superuser and selected_month:
        month_date = parse_month_filter(selected_month)
        if month_date:
            orders_list = orders_list.filter(order_date__year=month_date.year, order_date__month=month_date.month)
        else:
            selected_month = ''
            messages.warning(request, 'Неверный формат месяца. Используйте YYYY-MM.')

    orders_list = orders_with_related(orders_list)

    paginator = Paginator(orders_list, 10)
    page_number = request.GET.get('page')

    try:
        orders = paginator.page(page_number)
    except PageNotAnInteger:
        orders = paginator.page(1)
    except EmptyPage:
        orders = paginator.page(paginator.num_pages)

    monthly_total = None
    monthly_orders_count = None
    monthly_admin_stats = []
    month_label = None

    if request.user.is_superuser:
        summary_month = month_date
        if summary_month is None:
            today = timezone.localdate()
            summary_month = datetime(year=today.year, month=today.month, day=1)

        month_label = summary_month.strftime('%m.%Y')
        monthly_scope = list(
            orders_with_related(
                Order.objects.filter(
                    order_date__year=summary_month.year,
                    order_date__month=summary_month.month,
                )
            )
        )
        monthly_total = sum((o.get_final_total for o in monthly_scope), Decimal('0.00'))
        monthly_orders_count = len(monthly_scope)

        grouped = defaultdict(lambda: {'orders_count': 0, 'total': Decimal('0.00')})
        for order in monthly_scope:
            username = order.user.username if order.user else '-'
            grouped[username]['orders_count'] += 1
            grouped[username]['total'] += order.get_final_total

        monthly_admin_stats = [
            {
                'user__username': username,
                'orders_count': data['orders_count'],
                'total': data['total'],
            }
            for username, data in grouped.items()
        ]
        monthly_admin_stats.sort(key=lambda x: x['total'], reverse=True)

    reminder_date = timezone.localdate() - timedelta(days=2)
    reminder_scope = Order.objects.all()
    reminder_title = 'Общие напоминания по трек-номерам'
    if request.user.is_staff and not request.user.is_superuser:
        reminder_scope = reminder_scope.filter(user=request.user)
        reminder_title = 'Ваши напоминания по трек-номерам'

    track_reminders_qs = orders_with_related(
        reminder_scope.filter(
            order_date__lte=reminder_date,
            status__in=[Order.Status.NO, Order.Status.berildi, Order.Status.yolda],
        ).filter(
            Q(track_number__isnull=True) | Q(track_number='')
        )
    ).order_by('order_date', '-created_at')
    track_reminders_count = track_reminders_qs.count()
    track_reminders = track_reminders_qs[:15]

    context = {
        'orders': orders,
        'selected_month': selected_month,
        'monthly_total': monthly_total,
        'monthly_orders_count': monthly_orders_count,
        'monthly_admin_stats': monthly_admin_stats,
        'month_label': month_label,
        'track_reminders': track_reminders,
        'track_reminders_count': track_reminders_count,
        'track_reminder_title': reminder_title,
    }
    return render(request, 'akmalexpress/orders.html', context)


@user_passes_test(is_active_superuser)
def profile_view(request, user):
    try:
        profile = User.objects.get(username=user)
    except ObjectDoesNotExist:
        messages.error(request, 'Пользователь не найден')
        return redirect('index')

    if not (profile.is_superuser or profile.is_staff or profile.is_active):
        messages.warning(request, 'Вы не имеете доступ к этому профилю')
        return redirect('index')

    profile_orders_qs = orders_with_related(
        Order.objects.filter(user=profile).order_by('-order_date', '-created_at')
    )
    profile_total_amount = sum((o.get_final_total for o in profile_orders_qs), Decimal('0.00'))

    paginator = Paginator(profile_orders_qs, 10)
    page_number = request.GET.get('page')

    try:
        orders = paginator.page(page_number)
    except PageNotAnInteger:
        orders = paginator.page(1)
    except EmptyPage:
        orders = paginator.page(paginator.num_pages)

    return render(
        request,
        'akmalexpress/profile.html',
        {
            'profile': profile,
            'orders': orders,
            'profile_total_amount': profile_total_amount,
        },
    )


def login_view(request):
    if request.user.is_authenticated:
        messages.error(request, "Ошибка")
        return redirect('/')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, 'Вы вошли в свой аккаунт')
            if user.is_staff and not user.is_superuser:
                reminder_date = timezone.localdate() - timedelta(days=2)
                pending_count = Order.objects.filter(
                    user=user,
                    order_date__lte=reminder_date,
                    status__in=[Order.Status.NO, Order.Status.berildi, Order.Status.yolda],
                ).filter(
                    Q(track_number__isnull=True) | Q(track_number='')
                ).count()
                if pending_count:
                    messages.info(
                        request,
                        f'У вас {pending_count} заказ(ов) без трек-номера старше 2 дней. Откройте список заказов и обновите их.',
                    )
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
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    user = get_object_or_404(User, id=user_id)
    if user.is_superuser:
        messages.warning(request, 'Суперпользователя нельзя деактивировать через эту форму.')
        return redirect('create_admin')

    action = request.POST.get('action')
    if action == 'activate':
        user.is_active = True
        user.is_staff = True
        user.save(update_fields=['is_active', 'is_staff'])
        messages.success(request, f"Модератор {user} активирован")
    elif action == 'deactivate':
        user.is_active = False
        user.is_staff = False
        user.save(update_fields=['is_active', 'is_staff'])
        messages.info(request, f"Модератор {user} деактивирован")

    return redirect('create_admin')


@superuser_required
def delete_admin(request, user_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    user = get_object_or_404(User, id=user_id)
    if user.is_superuser:
        messages.warning(request, 'Суперпользователя удалять через эту форму нельзя.')
        return redirect('create_admin')

    if user == request.user:
        messages.warning(request, 'Нельзя удалить текущего пользователя.')
        return redirect('create_admin')

    username = user.username
    user.delete()
    messages.success(request, f'Админ @{username} удален')
    return redirect('create_admin')


@superuser_required
def create_admin(request):
    users = User.objects.exclude(is_superuser=True).order_by('username')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        user = User.objects.filter(username=username)

        if not user:
            if username and password1 == password2:
                created_user = User.objects.create_user(username=username, password=password1)
                created_user.is_staff = True
                created_user.is_active = True
                created_user.save(update_fields=['is_staff', 'is_active'])
                messages.success(request, f"Модератор @{username} успешно добавлен")
                return redirect('create_admin')

            messages.warning(request, "Пароли не совпадают или не указано имя пользователя")
            return redirect('create_admin')

        messages.warning(request, f"Пользователь с ником {username} уже существует!")
        return redirect('create_admin')

    return render(request, 'akmalexpress/create_admin.html', {'users': users})
