from django.contrib import messages
from django.contrib.auth.models import User
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _

from .services.admins import (
    ADMIN_ACCOUNT_STATUS_OPTIONS,
    ADMIN_ORDER_STATUS_OPTIONS,
    ADMIN_PERIOD_OPTIONS,
    build_admin_analytics,
    get_filtered_admin_users,
    resolve_admin_period,
)
from .view_helpers import superuser_required


@superuser_required
def toggle_status(request, user_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    user = get_object_or_404(User, id=user_id)
    if user.is_superuser:
        messages.warning(request, _('Суперпользователя нельзя деактивировать через эту форму.'))
        return redirect('create_admin')

    action = request.POST.get('action')
    if action == 'activate':
        user.is_active = True
        user.is_staff = True
        user.save(update_fields=['is_active', 'is_staff'])
        messages.success(request, _("Модератор %(user)s активирован") % {'user': user})
    elif action == 'deactivate':
        user.is_active = False
        user.is_staff = False
        user.save(update_fields=['is_active', 'is_staff'])
        messages.info(request, _("Модератор %(user)s деактивирован") % {'user': user})

    return redirect('create_admin')


@superuser_required
def delete_admin(request, user_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    user = get_object_or_404(User, id=user_id)
    if user.is_superuser:
        messages.warning(request, _('Суперпользователя удалять через эту форму нельзя.'))
        return redirect('create_admin')

    if user == request.user:
        messages.warning(request, _('Нельзя удалить текущего пользователя.'))
        return redirect('create_admin')

    username = user.username
    user.delete()
    messages.success(request, _('Админ @%(username)s удален') % {'username': username})
    return redirect('create_admin')


@superuser_required
def create_admin(request):
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
                messages.success(request, _("Модератор @%(username)s успешно добавлен") % {'username': username})
                return redirect('create_admin')

            messages.warning(request, _("Пароли не совпадают или не указано имя пользователя"))
            return redirect('create_admin')

        messages.warning(request, _("Пользователь с ником %(username)s уже существует!") % {'username': username})
        return redirect('create_admin')

    account_status = (request.GET.get('account_status') or 'all').strip()
    order_status = (request.GET.get('order_status') or 'all').strip()
    period = (request.GET.get('period') or 'month').strip()
    selected_admin_raw = (request.GET.get('admin_id') or 'all').strip()
    date_from_raw = (request.GET.get('date_from') or '').strip()
    date_to_raw = (request.GET.get('date_to') or '').strip()

    if account_status not in {key for key, _ in ADMIN_ACCOUNT_STATUS_OPTIONS}:
        account_status = 'all'
    if order_status not in {key for key, _ in ADMIN_ORDER_STATUS_OPTIONS}:
        order_status = 'all'

    period, date_from, date_to, period_errors = resolve_admin_period(period, date_from_raw, date_to_raw)
    for error_text in period_errors:
        messages.warning(request, error_text)

    available_users = get_filtered_admin_users(account_status=account_status)
    selected_admin_id = None
    if selected_admin_raw != 'all':
        try:
            selected_admin_id = int(selected_admin_raw)
        except (TypeError, ValueError):
            selected_admin_id = None
            selected_admin_raw = 'all'

    if selected_admin_id is not None:
        filtered_users = [user for user in available_users if user.id == selected_admin_id]
        if filtered_users:
            users = filtered_users
        else:
            messages.warning(request, _('Выбранный администратор не найден в текущем фильтре.'))
            selected_admin_raw = 'all'
            users = available_users
    else:
        users = available_users
    admin_rows, summary = build_admin_analytics(
        users=users,
        date_from=date_from,
        date_to=date_to,
        sort='orders_desc',
        order_status=order_status,
    )

    return render(
        request,
        'akmalexpress/create_admin.html',
        {
            'admin_rows': admin_rows,
            'admin_count': len(admin_rows),
            'summary': summary,
            'admin_period_options': ADMIN_PERIOD_OPTIONS,
            'admin_account_status_options': ADMIN_ACCOUNT_STATUS_OPTIONS,
            'admin_order_status_options': ADMIN_ORDER_STATUS_OPTIONS,
            'admin_filter_users': available_users,
            'filters': {
                'account_status': account_status,
                'order_status': order_status,
                'period': period,
                'admin_id': selected_admin_raw,
                'date_from': date_from.strftime('%Y-%m-%d') if date_from else '',
                'date_to': date_to.strftime('%Y-%m-%d') if date_to else '',
            },
        },
    )
