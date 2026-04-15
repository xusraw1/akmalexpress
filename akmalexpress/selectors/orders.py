"""Reusable order query helpers.

Selectors in this module are intentionally side-effect free and can be reused
from multiple views (public search, admin list, profile list, exports).
"""

from datetime import datetime

from django.db.models import Exists, OuterRef, Prefetch, Q

from ..models import OrderAttachment, OrderItem


def orders_with_related(queryset, *, include_attachments=False):
    """Attach only required related entities to reduce N+1 and memory pressure."""
    items_qs = OrderItem.objects.only(
        'id',
        'order_id',
        'product_name',
        'product_quantity',
        'product_price_currency',
        'product_price',
        'shipping_method',
        'track_number',
        'store',
        'link',
        'created_at',
        'updated_at',
    )
    qs = queryset.select_related('product', 'user').prefetch_related(
        Prefetch('items', queryset=items_qs)
    )
    if include_attachments:
        attachments_qs = OrderAttachment.objects.only('id', 'order_id', 'image', 'created_at')
        qs = qs.prefetch_related(Prefetch('attachments', queryset=attachments_qs))
    return qs


def parse_month_filter(value):
    """Parse YYYY-MM from query params."""
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m')
    except ValueError:
        return None


def parse_date_filter(value):
    """Parse YYYY-MM-DD from query params."""
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        return None


def _normalize_whitespace(value):
    return ' '.join((value or '').split())


def _normalize_phone(value):
    return ''.join(char for char in str(value or '') if char.isdigit())


def parse_checkbox_flag(value):
    normalized = str(value or '').strip().lower()
    return normalized in {'1', 'true', 'on', 'yes'}


def _build_public_search_q(search_query):
    """Build strict OR-search query for public search form.

    Matching is intentionally conservative (exact for name/phone/track/receipt)
    to avoid exposing unrelated orders in customer-facing search.
    """
    cleaned = _normalize_whitespace(search_query)
    if not cleaned:
        return Q(pk__in=[])

    search_filter = Q()
    has_conditions = False

    if cleaned.isdigit():
        search_filter |= Q(receipt_number=int(cleaned))
        has_conditions = True

    phone_digits = _normalize_phone(cleaned)
    if phone_digits:
        try:
            phone_value = int(phone_digits)
        except ValueError:
            phone_value = None
        if phone_value is not None:
            search_filter |= Q(phone1=phone_value) | Q(phone2=phone_value)
            has_conditions = True

    name_parts = cleaned.split()
    if len(name_parts) >= 2:
        first_name = name_parts[0]
        last_name = ' '.join(name_parts[1:])
        search_filter |= Q(first_name__iexact=first_name, last_name__iexact=last_name)
        search_filter |= Q(first_name__iexact=last_name, last_name__iexact=first_name)
        has_conditions = True
    elif len(name_parts) == 1:
        token = name_parts[0]
        search_filter |= Q(first_name__iexact=token) | Q(last_name__iexact=token)
        has_conditions = True

    # Track number should be exact for public search results.
    # Prefer item-level tracking, keep legacy order-level fallback.
    search_filter |= Q(items__track_number__iexact=cleaned) | Q(track_number__iexact=cleaned)
    has_conditions = True

    if not has_conditions:
        return Q(pk__in=[])
    return search_filter


def apply_public_order_search_filter(queryset, search_query):
    """Exact public search: receipt number, full name, phone, or track number."""
    cleaned = _normalize_whitespace(search_query)
    if not cleaned:
        return queryset
    return queryset.filter(_build_public_search_q(cleaned))


def _base_search_q(search_query):
    """Common fuzzy search clause used in authenticated admin interfaces."""
    return (
        Q(receipt_number__icontains=search_query)
        | Q(first_name__icontains=search_query)
        | Q(last_name__icontains=search_query)
        | Q(items__product_name__icontains=search_query)
        | Q(product__product_name__icontains=search_query)
    )


def apply_order_search_filter(queryset, search_query, *, include_phone=False, include_track=False):
    """Apply reusable order search clauses with optional phone/track fields."""
    cleaned_search = (search_query or '').strip()
    if not cleaned_search:
        return queryset

    search_filter = _base_search_q(cleaned_search)
    if include_phone:
        search_filter |= Q(phone1__icontains=cleaned_search) | Q(phone2__icontains=cleaned_search)
    if include_track:
        search_filter |= Q(items__track_number__icontains=cleaned_search) | Q(track_number__icontains=cleaned_search)

    return queryset.filter(search_filter)


def apply_missing_track_filter(queryset, enabled=False):
    """
    Return orders that still need track numbers.

    Rule:
    - at least one item without track number, or
    - order without items and empty legacy order track.
    """
    if not enabled:
        return queryset

    order_items = OrderItem.objects.filter(order_id=OuterRef('pk'))
    items_without_track = order_items.filter(Q(track_number__isnull=True) | Q(track_number=''))

    return queryset.annotate(
        _missing_track_has_items=Exists(order_items),
        _missing_track_has_item_without_track=Exists(items_without_track),
    ).filter(
        Q(_missing_track_has_item_without_track=True)
        | Q(_missing_track_has_items=False, track_number__isnull=True)
        | Q(_missing_track_has_items=False, track_number='')
    )
