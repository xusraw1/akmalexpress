from datetime import datetime, timedelta

from django.db.models import Count, Exists, OuterRef, Prefetch, Q
from django.utils import timezone

from ..models import Order, OrderAttachment, OrderItem


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
    Return orders that still need track numbers:
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


def build_stuck_orders_snapshot(queryset, *, limit=8):
    """
    Build compact data for orders that are likely stuck in non-final statuses.
    Thresholds are intentionally conservative to avoid false positives.
    """
    today = timezone.localdate()
    thresholds_by_status = {
        Order.Status.ACCEPTED: 3,
        Order.Status.ORDERED: 10,
        Order.Status.TRANSIT: 20,
    }

    overdue_q = Q(pk__in=[])
    for status_code, threshold_days in thresholds_by_status.items():
        cutoff_date = today - timedelta(days=threshold_days)
        overdue_q |= Q(status=status_code, order_date__lt=cutoff_date)

    overdue_qs = queryset.filter(overdue_q).order_by('order_date', 'receipt_number')
    overdue_total = overdue_qs.count()

    status_totals = {code: 0 for code in thresholds_by_status}
    for row in overdue_qs.values('status').annotate(total=Count('id')):
        if row['status'] in status_totals:
            status_totals[row['status']] = row['total']

    rows = []
    for order in overdue_qs.only(
        'id',
        'slug',
        'receipt_number',
        'status',
        'order_date',
        'first_name',
        'last_name',
    )[:limit]:
        age_days = max(0, (today - order.order_date).days)
        threshold_days = thresholds_by_status.get(order.status, 0)
        age_over_threshold = max(0, age_days - threshold_days)
        severity = 'critical' if age_over_threshold >= 7 else 'warning'

        rows.append(
            {
                'slug': order.slug,
                'receipt_number': order.receipt_number,
                'full_name': f"{order.first_name} {order.last_name}".strip(),
                'status_code': order.status,
                'status_label': order.get_status_display(),
                'age_days': age_days,
                'threshold_days': threshold_days,
                'age_over_threshold': age_over_threshold,
                'severity': severity,
            }
        )

    return {
        'total': overdue_total,
        'limit': limit,
        'rows': rows,
        'has_more': overdue_total > len(rows),
        'by_status': status_totals,
        'thresholds_by_status': thresholds_by_status,
    }
