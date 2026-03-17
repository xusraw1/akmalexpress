from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.db.models import Max, Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from akmalexpress.models import Order
from akmalexpress.selectors.orders import orders_with_related, parse_date_filter

ADMIN_PERIOD_OPTIONS = [
    ('day', _('За день')),
    ('week', _('За неделю')),
    ('month', _('За месяц')),
    ('custom', _('Произвольный диапазон')),
]

ADMIN_ACCOUNT_STATUS_OPTIONS = [
    ('all', _('Все аккаунты')),
    ('active', _('Активен')),
    ('inactive', _('Деактивирован')),
]

ADMIN_ORDER_STATUS_OPTIONS = [
    ('all', _('Все статусы')),
    (Order.Status.ACCEPTED, _('Заказан / Ожидает обработки')),
    (Order.Status.ORDERED, _('В обработке')),
    (Order.Status.TRANSIT, _('Отправлен')),
    (Order.Status.ARRIVED, _('Доставлен')),
    (Order.Status.CANCELLED, _('Отменён')),
]


def resolve_admin_period(period, date_from_raw='', date_to_raw=''):
    today = timezone.localdate()
    date_from = parse_date_filter(date_from_raw)
    date_to = parse_date_filter(date_to_raw)
    resolved_period = period if period in {key for key, _ in ADMIN_PERIOD_OPTIONS} else 'month'
    errors = []

    if resolved_period == 'day':
        date_from = today
        date_to = today
    elif resolved_period == 'week':
        date_from = today - timedelta(days=6)
        date_to = today
    elif resolved_period == 'month':
        date_from = today.replace(day=1)
        date_to = today
    elif resolved_period == 'custom':
        if date_from_raw and not date_from:
            errors.append(_('Неверный формат даты "от". Используйте YYYY-MM-DD.'))
        if date_to_raw and not date_to:
            errors.append(_('Неверный формат даты "до". Используйте YYYY-MM-DD.'))
        if not date_from and not date_to:
            errors.append(_('Для произвольного диапазона укажите дату "от" или "до".'))

    if date_from and date_to and date_from > date_to:
        date_from, date_to = date_to, date_from

    return resolved_period, date_from, date_to, errors


def get_filtered_admin_users(search='', account_status='all'):
    users_qs = User.objects.exclude(is_superuser=True)
    if search:
        users_qs = users_qs.filter(
            Q(username__icontains=search)
            | Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
        )
    if account_status == 'active':
        users_qs = users_qs.filter(is_active=True)
    elif account_status == 'inactive':
        users_qs = users_qs.filter(is_active=False)
    return list(users_qs.order_by('username'))


def build_admin_analytics(users, date_from=None, date_to=None, sort='orders_desc', order_status='all'):
    period_orders_qs = orders_with_related(Order.objects.filter(user__in=users))
    if date_from:
        period_orders_qs = period_orders_qs.filter(order_date__gte=date_from)
    if date_to:
        period_orders_qs = period_orders_qs.filter(order_date__lte=date_to)
    if order_status and order_status != 'all':
        period_orders_qs = period_orders_qs.filter(status=order_status)

    stats = defaultdict(
        lambda: {
            'processed_orders': 0,
            'completed_orders': 0,
            'cancelled_orders': 0,
            'processing_orders': 0,
            'total_amount': Decimal('0.00'),
        }
    )
    processing_statuses = {Order.Status.ACCEPTED, Order.Status.ORDERED, Order.Status.TRANSIT}
    for order in period_orders_qs:
        if not order.user_id:
            continue
        item = stats[order.user_id]
        item['processed_orders'] += 1
        if order.status == Order.Status.ARRIVED:
            item['completed_orders'] += 1
        elif order.status == Order.Status.CANCELLED:
            item['cancelled_orders'] += 1
        elif order.status in processing_statuses:
            item['processing_orders'] += 1
        item['total_amount'] += order.get_final_total

    last_activity_map = {
        item['user']: item['last_activity']
        for item in (
            Order.objects.filter(user__in=users)
            .values('user')
            .annotate(last_activity=Max('updated_at'))
        )
    }

    admin_rows = []
    for admin_user in users:
        item = stats[admin_user.id]
        admin_rows.append(
            {
                'user': admin_user,
                'processed_orders': item['processed_orders'],
                'completed_orders': item['completed_orders'],
                'cancelled_orders': item['cancelled_orders'],
                'processing_orders': item['processing_orders'],
                'total_amount': item['total_amount'],
                'last_activity': last_activity_map.get(admin_user.id),
            }
        )

    if sort == 'orders_asc':
        admin_rows.sort(key=lambda row: (row['processed_orders'], row['user'].date_joined, row['user'].username))
    elif sort == 'joined_desc':
        admin_rows.sort(key=lambda row: (row['user'].date_joined, row['user'].username), reverse=True)
    elif sort == 'joined_asc':
        admin_rows.sort(key=lambda row: (row['user'].date_joined, row['user'].username))
    else:
        admin_rows.sort(key=lambda row: (row['processed_orders'], row['user'].date_joined), reverse=True)

    summary = {
        'processed': sum(row['processed_orders'] for row in admin_rows),
        'completed': sum(row['completed_orders'] for row in admin_rows),
        'cancelled': sum(row['cancelled_orders'] for row in admin_rows),
        'processing': sum(row['processing_orders'] for row in admin_rows),
        'total_amount': sum((row['total_amount'] for row in admin_rows), Decimal('0.00')),
    }

    return admin_rows, summary
