"""Cross-view helper functions and access decorators.

This module contains shared logic that does not fit a single feature view:
URL safety, profile filter options, formset shaping, and access wrappers.
"""

from datetime import timedelta
from decimal import Decimal, InvalidOperation
from functools import wraps
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from django.contrib import messages
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _

from .models import Order, UserProfile
from .selectors.orders import parse_date_filter


def configure_order_item_formset(item_formset):
    """Hide DELETE controls; rows are managed by custom UI buttons."""
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


def _to_decimal(value, default='0.00'):
    if value in (None, ''):
        return Decimal(default)
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def _to_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}


def _build_order_item_initial(order):
    """Build initial formset payload for editing an order with legacy fallback."""
    existing_items = list(order.items.all())
    if existing_items:
        return [
            {
                'product_name': item.product_name,
                'product_quantity': item.product_quantity,
                'product_price_currency': item.product_price_currency,
                'product_price': item.product_price,
                'shipping_method': item.shipping_method or order.shipping_method,
                'track_number': item.track_number or '',
                'store': item.store,
                'link': item.link,
            }
            for item in existing_items
        ]

    if order.product:
        return [
            {
                'product_name': order.product.product_name,
                'product_quantity': order.product.product_quantity,
                'product_price_currency': order.product.product_price_currency,
                'product_price': order.product.product_price,
                'shipping_method': order.shipping_method,
                'track_number': order.track_number or '',
                'store': order.product.store,
                'link': order.product.link,
            }
        ]

    return []


def _calculate_order_totals_payload(payload):
    """Compute auto total from line items with per-order exchange rates.

    Returns quantized UZS totals for UI preview/API usage.
    """
    usd_rate = _to_decimal(payload.get('usd_rate'), '0.00')
    rmb_rate = _to_decimal(payload.get('rmb_rate'), '0.00')
    items = payload.get('items') or []
    active_items = []
    items_total = Decimal('0.00')

    for item in items:
        if not isinstance(item, dict):
            continue
        if _to_bool(item.get('delete')):
            continue

        quantity = _to_decimal(item.get('quantity'), '0')
        price = _to_decimal(item.get('price'), '0')
        if quantity <= 0 or price < 0:
            continue

        subtotal = quantity * price
        currency = str(item.get('currency') or 'UZS').upper()
        if currency == 'USD':
            subtotal *= usd_rate
        elif currency == 'RMB':
            subtotal *= rmb_rate
        items_total += subtotal
        active_items.append(item)

    stores = [str(item.get('store') or '') for item in active_items if item.get('store')]
    aliexpress_only = bool(stores) and all(store == 'AliExpress' for store in stores)
    extra_total = Decimal('0.00')
    auto_total = items_total
    return {
        'items_total': items_total.quantize(Decimal('0.01')),
        'extra_total': extra_total.quantize(Decimal('0.01')),
        'auto_total': auto_total.quantize(Decimal('0.01')),
        'aliexpress_only': aliexpress_only,
    }


PROFILE_STATUS_OPTIONS = [
    ('all', _('Все заказы')),
    ('queued', _('Заказан / Ожидает обработки')),
    ('processing', _('В обработке')),
    ('shipped', _('Отправлен')),
    ('delivered', _('Доставлен')),
    ('cancelled', _('Отменён')),
]

PROFILE_STATUS_FILTER_MAP = {
    'queued': [Order.Status.ACCEPTED],
    'processing': [Order.Status.ORDERED],
    'shipped': [Order.Status.TRANSIT],
    'delivered': [Order.Status.ARRIVED],
    'cancelled': [Order.Status.CANCELLED],
}

PROFILE_PERIOD_OPTIONS = [
    ('all', _('Все время')),
    ('today', _('За сегодня')),
    ('last_7_days', _('За последние 7 дней')),
    ('current_month', _('За текущий месяц')),
    ('custom', _('Произвольный диапазон')),
]


def _get_or_create_user_profile(user):
    """Return existing user profile or create an empty one."""
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def _resolve_profile_period(period, date_from_raw='', date_to_raw=''):
    """Normalize profile period filter and validate optional custom dates."""
    today = timezone.localdate()
    date_from = parse_date_filter(date_from_raw)
    date_to = parse_date_filter(date_to_raw)
    resolved_period = period if period in {key for key, _ in PROFILE_PERIOD_OPTIONS} else 'all'
    errors = []

    if resolved_period == 'today':
        date_from = today
        date_to = today
    elif resolved_period == 'last_7_days':
        date_from = today - timedelta(days=6)
        date_to = today
    elif resolved_period == 'current_month':
        date_from = today.replace(day=1)
        date_to = today
    elif resolved_period == 'custom':
        if date_from_raw and not date_from:
            errors.append(_('Неверный формат даты "от". Используйте YYYY-MM-DD.'))
        if date_to_raw and not date_to:
            errors.append(_('Неверный формат даты "до". Используйте YYYY-MM-DD.'))
        if not date_from and not date_to:
            errors.append(_('Для произвольного диапазона укажите дату "от" или "до".'))
    else:
        if date_from_raw and not date_from:
            errors.append(_('Неверный формат даты "от". Используйте YYYY-MM-DD.'))
        if date_to_raw and not date_to:
            errors.append(_('Неверный формат даты "до". Используйте YYYY-MM-DD.'))

    if date_from and date_to and date_from > date_to:
        date_from, date_to = date_to, date_from

    return resolved_period, date_from, date_to, errors


def _safe_next_redirect(request, fallback_url, include_referer=True):
    """Return validated local redirect URL and strip legacy language artifacts.

    Security note:
    - Blocks open redirects by validating host/scheme.
    - Removes legacy `/ru/...` prefixes and duplicated `lang` query params.
    """
    candidates = [request.POST.get('next'), request.GET.get('next')]
    if include_referer:
        candidates.append(request.META.get('HTTP_REFERER'))
    candidates.append(fallback_url)
    next_url = next((url for url in candidates if url), fallback_url)
    if not url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return fallback_url

    parsed_next = urlparse(next_url)
    cleaned_path = parsed_next.path or '/'
    if cleaned_path == '/ru':
        cleaned_path = '/'
    elif cleaned_path.startswith('/ru/'):
        cleaned_path = f"/{cleaned_path.removeprefix('/ru/')}"
    clean_query = [(key, value) for key, value in parse_qsl(parsed_next.query, keep_blank_values=True) if key != 'lang']
    cleaned_url = urlunparse(
        parsed_next._replace(
            path=cleaned_path,
            query=urlencode(clean_query, doseq=True),
        )
    )
    if not url_has_allowed_host_and_scheme(
        cleaned_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return fallback_url
    return cleaned_url


def is_active_superuser(user):
    """Project-level predicate for any authenticated staff account."""
    return bool(user.is_authenticated and user.is_active and (user.is_staff or user.is_superuser))


def user_is_order_creator(view_func):
    """Allow access to order owner, staff, or superuser only."""
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
    """Restrict access to superusers and redirect with flash message otherwise."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, "У вас нет прав для доступа к этой странице")
            return redirect('/')
        return view_func(request, *args, **kwargs)

    return _wrapped_view
