import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from zipfile import BadZipFile
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Q
from django.http import HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.html import format_html
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from .forms import (
    ChangeOrderForm,
    CreateOrderForm,
    OrderItemFormSet,
    resolve_manual_total_value,
    save_order_items,
)
from .models import Order, OrderItem
from .selectors.orders import (
    apply_missing_track_filter,
    apply_order_search_filter,
    build_stuck_orders_snapshot,
    orders_with_related,
    parse_checkbox_flag,
    parse_month_filter,
)
from .services.excel import (
    _build_export_filename,
    _build_orders_workbook,
    _excel_workbook_response,
    _import_orders_from_workbook,
)
from .services.images import optimize_uploaded_image
from .view_helpers import (
    _build_order_item_initial,
    _calculate_order_totals_payload,
    _safe_next_redirect,
    configure_order_item_formset,
    is_active_superuser,
    user_is_order_creator,
)

TRACK_QUEUE_PAGE_SIZE = 15
SERVICE_THRESHOLD_SUM = Decimal('70000')
SERVICE_FLAT_LOW = Decimal('10000')
SERVICE_RATE_HIGH = Decimal('0.15')
SERVICE_RATE_TEN = Decimal('0.10')
SERVICE_RATE_HUNDRED = Decimal('100')
SERVICE_MODE_AUTO = 'auto'
SERVICE_MODE_FLAT = 'fixed_10000'
SERVICE_MODE_PERCENT_10 = 'percent_10'
SERVICE_MODE_PERCENT_15 = 'percent_15'
SERVICE_MODE_CUSTOM_PERCENT = 'custom_percent'
SERVICE_MODES = {
    SERVICE_MODE_AUTO,
    SERVICE_MODE_FLAT,
    SERVICE_MODE_PERCENT_10,
    SERVICE_MODE_PERCENT_15,
    SERVICE_MODE_CUSTOM_PERCENT,
}


def _normalize_track_number(raw_value):
    return ''.join((raw_value or '').strip().upper().split())


def _parse_bulk_order_ids(raw_values):
    parsed_ids = []
    for raw_value in raw_values:
        value = str(raw_value or '').strip()
        if value.isdigit():
            parsed_ids.append(int(value))
    return sorted(set(parsed_ids))


def _order_has_any_track(order):
    has_item_track = order.items.exclude(track_number__isnull=True).exclude(track_number='').exists()
    if has_item_track:
        return True
    return bool((order.track_number or '').strip())


def _promote_status_to_transit_if_track_added(order, *, had_track_before=False):
    has_track_now = _order_has_any_track(order)
    if had_track_before or not has_track_now:
        return False
    if order.status not in {Order.Status.ACCEPTED, Order.Status.ORDERED}:
        return False

    order.status = Order.Status.TRANSIT
    update_fields = ['status', 'updated_at']
    if order.come is not None:
        order.come = None
        update_fields.append('come')
    order.save(update_fields=update_fields)
    return True


def _parse_sheet_decimal(raw_value, default='0'):
    normalized = str(raw_value or '').replace(' ', '').replace(',', '.').strip()
    if not normalized:
        return Decimal(default)
    try:
        parsed = Decimal(normalized)
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(default)
    if parsed < 0:
        return Decimal(default)
    return parsed


def _parse_service_mode(raw_value):
    mode = (raw_value or SERVICE_MODE_PERCENT_15).strip()
    if mode not in SERVICE_MODES:
        return SERVICE_MODE_PERCENT_15
    return mode


def _parse_service_percent(raw_value, default='15'):
    normalized = str(raw_value or '').replace(' ', '').replace(',', '.').strip()
    if not normalized:
        return Decimal(default)
    try:
        parsed = Decimal(normalized)
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(default)
    if parsed <= 0:
        return Decimal(default)
    if parsed > 100:
        return Decimal('100')
    return parsed


def _calculate_service_cost(product_cost, cargo_cost, mode=SERVICE_MODE_PERCENT_15, custom_percent=None):
    base_sum = (product_cost or Decimal('0')) + (cargo_cost or Decimal('0'))
    service_mode = _parse_service_mode(mode)
    service_cost = Decimal('0')

    if service_mode == SERVICE_MODE_FLAT:
        service_cost = SERVICE_FLAT_LOW
    elif service_mode == SERVICE_MODE_PERCENT_10:
        service_cost = base_sum * SERVICE_RATE_TEN
    elif service_mode == SERVICE_MODE_CUSTOM_PERCENT:
        percent = _parse_service_percent(custom_percent, default='15')
        service_cost = base_sum * (percent / SERVICE_RATE_HUNDRED)
    elif service_mode == SERVICE_MODE_AUTO:
        service_cost = SERVICE_FLAT_LOW if base_sum < SERVICE_THRESHOLD_SUM else (base_sum * SERVICE_RATE_HIGH)
    else:
        service_cost = base_sum * SERVICE_RATE_HIGH

    if base_sum > 0 and service_cost < SERVICE_FLAT_LOW:
        service_cost = SERVICE_FLAT_LOW

    return service_cost.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _build_settlement_initial(order):
    full_name = f"{(order.first_name or '').strip()} {(order.last_name or '').strip()}".strip()
    product_cost = Decimal(order.get_total_price or '0')
    cargo_cost = Decimal('0')
    service_percent = Decimal('15')
    service_cost = _calculate_service_cost(product_cost, cargo_cost, SERVICE_MODE_PERCENT_15, service_percent)
    return {
        'receipt_number': str(order.receipt_number),
        'full_name': full_name,
        'product_cost': product_cost,
        'cargo_cost': cargo_cost,
        'service_mode': SERVICE_MODE_PERCENT_15,
        'service_percent': service_percent,
        'service_cost': service_cost,
        'total_amount': product_cost + cargo_cost + service_cost,
        'due_amount': cargo_cost + service_cost,
        'phone': str(order.phone1 or ''),
    }


def detail_order(request, slug):
    order = get_object_or_404(orders_with_related(Order.objects.all(), include_attachments=True), slug=slug)
    if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
        return render(request, 'akmalexpress/detail_order.html', {'order': order})
    return render(request, 'akmalexpress/client_order_detail.html', {'order': order})


@user_passes_test(is_active_superuser)
def print_receipt(request, slug):
    order = get_object_or_404(orders_with_related(Order.objects.all(), include_attachments=True), slug=slug)
    return render(request, 'akmalexpress/receipt_print.html', {'order': order})


@user_passes_test(is_active_superuser)
def print_settlement_sheet(request, slug):
    order = get_object_or_404(orders_with_related(Order.objects.all(), include_attachments=True), slug=slug)
    sheet = _build_settlement_initial(order)

    if request.method == 'POST':
        receipt_number = (request.POST.get('receipt_number') or sheet['receipt_number']).strip() or sheet['receipt_number']
        full_name = (request.POST.get('full_name') or sheet['full_name']).strip() or sheet['full_name']
        phone = (request.POST.get('phone') or sheet['phone']).strip()
        service_mode = _parse_service_mode(request.POST.get('service_mode'))
        service_percent = _parse_service_percent(request.POST.get('service_percent'), default=sheet.get('service_percent', 15))

        product_cost = _parse_sheet_decimal(request.POST.get('product_cost'), default=sheet['product_cost'])
        cargo_cost = _parse_sheet_decimal(request.POST.get('cargo_cost'), default='0')
        service_cost = _calculate_service_cost(product_cost, cargo_cost, service_mode, service_percent)
        total_amount = product_cost + cargo_cost + service_cost
        due_amount = cargo_cost + service_cost

        sheet = {
            'receipt_number': receipt_number,
            'full_name': full_name,
            'phone': phone,
            'product_cost': product_cost,
            'cargo_cost': cargo_cost,
            'service_mode': service_mode,
            'service_percent': service_percent,
            'service_cost': service_cost,
            'total_amount': total_amount,
            'due_amount': due_amount,
        }
        return render(
            request,
            'akmalexpress/settlement_print.html',
            {
                'order': order,
                'sheet': sheet,
            },
        )

    return render(
        request,
        'akmalexpress/settlement_form.html',
        {
            'order': order,
            'sheet': sheet,
        },
    )


@user_passes_test(is_active_superuser)
@user_is_order_creator
def delete_order(request, slug):
    order = get_object_or_404(Order, slug=slug)
    if request.method == 'POST':
        order.delete()
        messages.success(request, _("Заказ с номером №%(receipt)s успешно удален") % {'receipt': order.receipt_number})
        return redirect('/')
    return render(request, 'akmalexpress/delete_order.html', {'order': order})


@user_passes_test(is_active_superuser)
@user_is_order_creator
def change_order(request, slug):
    orderr = get_object_or_404(Order, slug=slug)
    form = ChangeOrderForm(instance=orderr)
    item_formset = configure_order_item_formset(
        OrderItemFormSet(prefix='items', initial=_build_order_item_initial(orderr))
    )

    if request.method == 'POST':
        has_item_formset_post = any(key.startswith('items-') for key in request.POST.keys())
        had_track_before = _order_has_any_track(orderr) if has_item_formset_post else False
        form = ChangeOrderForm(request.POST, request.FILES, instance=orderr)
        if has_item_formset_post:
            item_formset = configure_order_item_formset(OrderItemFormSet(request.POST, prefix='items'))

        formset_is_valid = item_formset.is_valid() if has_item_formset_post else True
        if form.is_valid() and formset_is_valid:
            order = form.save(commit=False)
            if has_item_formset_post:
                order.product = None
                order.manual_total = resolve_manual_total_value(form, item_formset)
            if order.status == Order.Status.ARRIVED:
                order.come = timezone.now()
            elif order.status != Order.Status.ARRIVED:
                order.come = None

            order.save()
            if has_item_formset_post:
                order.items.all().delete()
                save_order_items(order, item_formset)
                if _promote_status_to_transit_if_track_added(order, had_track_before=had_track_before):
                    messages.info(
                        request,
                        _('Трек-номер добавлен: статус заказа автоматически изменен на «В пути».'),
                    )

            remove_attachment_ids = []
            for raw_id in request.POST.getlist('remove_attachment_ids'):
                if str(raw_id).isdigit():
                    remove_attachment_ids.append(int(raw_id))

            if remove_attachment_ids:
                for attachment in order.attachments.filter(id__in=remove_attachment_ids):
                    if attachment.image:
                        attachment.image.delete(save=False)
                    attachment.delete()

            for image in form.cleaned_data.get('attachments', []):
                optimized_image = optimize_uploaded_image(image, max_size=(1800, 1800), quality=84)
                order.attachments.create(image=optimized_image)

            messages.success(request, _("Заказ с квитанцией №%(receipt)s обновлен") % {'receipt': order.receipt_number})
            return redirect('orders')

        messages.warning(request, _('Проверьте форму: есть ошибки в данных заказа или товаров.'))

    return render(
        request,
        'akmalexpress/change_order.html',
        {
            'form': form,
            'orderr': orderr,
            'item_formset': item_formset,
        },
    )


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
            form.cleaned_data['manual_total'] = resolve_manual_total_value(form, item_formset)
            order = form.save_order(user=request.user)
            save_order_items(order, item_formset)
            if _promote_status_to_transit_if_track_added(order, had_track_before=False):
                messages.info(
                    request,
                    _('Трек-номер добавлен: статус заказа автоматически изменен на «В пути».'),
                )

            messages.success(request, _('Заказ №%(receipt)s успешно создан') % {'receipt': order.receipt_number})

            return redirect('orders')

        messages.warning(request, _('Проверьте форму: есть ошибки в данных заказа или товаров.'))

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
def order_total_preview(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    try:
        payload = json.loads(request.body.decode('utf-8')) if request.body else {}
        if not isinstance(payload, dict):
            payload = {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'error': 'invalid_payload'}, status=400)

    totals = _calculate_order_totals_payload(payload)
    return JsonResponse(
        {
            'items_total': f"{totals['items_total']:.2f}",
            'extra_total': f"{totals['extra_total']:.2f}",
            'auto_total': f"{totals['auto_total']:.2f}",
            'aliexpress_only': totals['aliexpress_only'],
        }
    )


@user_passes_test(is_active_superuser)
def create_product(request):
    messages.info(request, _('Создание товара перенесено в единую форму создания заказа.'))
    return redirect('create_order')


@user_passes_test(is_active_superuser)
def order_list(request):
    if request.method == 'POST':
        fallback_url = reverse('orders')
        next_url = _safe_next_redirect(request, fallback_url)
        selected_ids = _parse_bulk_order_ids(request.POST.getlist('order_ids'))
        requested_status = (request.POST.get('bulk_status') or '').strip()
        available_statuses = {choice[0] for choice in Order.Status.choices}

        if not selected_ids:
            messages.warning(request, _('Для bulk-режима выберите хотя бы один заказ.'))
            return redirect(next_url)

        if requested_status not in available_statuses:
            messages.warning(request, _('Выберите корректный статус для массового обновления.'))
            return redirect(next_url)

        selected_orders = Order.objects.filter(id__in=selected_ids).only('id', 'receipt_number', 'status', 'come')
        updated_count = 0
        for order in selected_orders:
            if order.status == requested_status:
                continue
            order.status = requested_status
            if requested_status == Order.Status.ARRIVED:
                order.come = timezone.now()
            elif order.come is not None:
                order.come = None
            order.save(update_fields=['status', 'come', 'updated_at'])
            updated_count += 1

        if updated_count:
            status_label = dict(Order.Status.choices).get(requested_status, requested_status)
            messages.success(
                request,
                _('Bulk-режим: обновлено заказов %(count)s, новый статус — %(status)s.') % {
                    'count': updated_count,
                    'status': status_label,
                },
            )
        else:
            messages.info(request, _('Bulk-режим: выбранные заказы уже имеют указанный статус.'))

        return redirect(next_url)

    orders_list = Order.objects.all()
    search_query = (request.GET.get('search') or '').strip()
    missing_track_only = parse_checkbox_flag(request.GET.get('missing_track'))
    orders_list = apply_order_search_filter(
        orders_list,
        search_query,
        include_phone=True,
        include_track=request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser),
    )
    orders_list = apply_missing_track_filter(orders_list, enabled=missing_track_only)

    selected_month = request.GET.get('month', '').strip()
    month_date = None
    if request.user.is_superuser and selected_month:
        month_date = parse_month_filter(selected_month)
        if month_date:
            orders_list = orders_list.filter(order_date__year=month_date.year, order_date__month=month_date.month)
        else:
            selected_month = ''
            messages.warning(request, _('Неверный формат месяца. Используйте YYYY-MM.'))

    filtered_orders_qs = orders_list.distinct()
    stuck_orders_snapshot = build_stuck_orders_snapshot(filtered_orders_qs, limit=8)
    orders_list = orders_with_related(
        filtered_orders_qs.order_by('-order_date', '-created_at')
    )

    paginator = Paginator(orders_list, 20)
    page_number = request.GET.get('page')

    try:
        orders = paginator.page(page_number)
    except PageNotAnInteger:
        orders = paginator.page(1)
    except EmptyPage:
        orders = paginator.page(paginator.num_pages)

    context = {
        'orders': orders,
        'search_query': search_query,
        'selected_month': selected_month,
        'missing_track_only': missing_track_only,
        'stuck_orders': stuck_orders_snapshot,
        'status_choices': Order.Status.choices,
    }
    return render(request, 'akmalexpress/orders.html', context)


@user_passes_test(is_active_superuser)
def track_center_view(request):
    list_search = (request.GET.get('q') or request.POST.get('q') or '').strip()
    selected_track = _normalize_track_number(request.GET.get('track') or request.POST.get('track'))
    available_statuses = {choice[0] for choice in Order.Status.choices}

    def build_redirect_url(extra_params=None):
        params = {}
        if list_search:
            params['q'] = list_search
        if extra_params:
            for key, value in extra_params.items():
                if value not in (None, ''):
                    params[key] = value
        base_url = reverse('track_center')
        return f"{base_url}?{urlencode(params)}" if params else base_url

    def find_track_match(track_number):
        if not track_number:
            return None
        matched_item = (
            OrderItem.objects.select_related('order')
            .only(
                'id',
                'product_name',
                'track_number',
                'updated_at',
                'order__id',
                'order__slug',
                'order__receipt_number',
                'order__first_name',
                'order__last_name',
                'order__status',
                'order__come',
                'order__order_date',
            )
            .filter(track_number__iexact=track_number)
            .order_by('-updated_at', '-id')
            .first()
        )
        if matched_item is not None:
            return {
                'order': matched_item.order,
                'item': matched_item,
                'track_number': matched_item.track_number,
                'product_name': matched_item.product_name,
            }

        legacy_order = (
            Order.objects.only(
                'id',
                'slug',
                'receipt_number',
                'first_name',
                'last_name',
                'status',
                'order_date',
                'come',
                'track_number',
                'updated_at',
            )
            .filter(track_number__iexact=track_number)
            .order_by('-updated_at', '-id')
            .first()
        )
        if legacy_order is not None:
            return {
                'order': legacy_order,
                'item': None,
                'track_number': legacy_order.track_number,
                'product_name': '',
            }
        return None

    if request.method == 'POST':
        action = (request.POST.get('action') or '').strip()
        if action == 'update_status':
            order_id = (request.POST.get('order_id') or '').strip()
            new_status = (request.POST.get('status') or '').strip()
            posted_track = _normalize_track_number(request.POST.get('track_number') or selected_track)

            if not order_id.isdigit():
                messages.error(request, _('Не удалось определить заказ для изменения статуса.'))
                return redirect(build_redirect_url({'track': posted_track}))

            matched_order = (
                Order.objects.only('id', 'receipt_number', 'status', 'track_number', 'come')
                .filter(id=int(order_id))
                .first()
            )
            if matched_order is None:
                messages.error(request, _('Заказ для изменения статуса не найден.'))
                return redirect(build_redirect_url({'track': posted_track}))

            if new_status not in available_statuses:
                messages.warning(request, _('Выберите корректный статус заказа.'))
                return redirect(build_redirect_url({'track': posted_track}))

            matched_order.status = new_status
            update_fields = ['status', 'updated_at']
            if new_status == Order.Status.ARRIVED:
                matched_order.come = timezone.now()
                update_fields.append('come')
            elif matched_order.come is not None:
                matched_order.come = None
                update_fields.append('come')
            matched_order.save(update_fields=update_fields)
            messages.success(
                request,
                _('Статус заказа №%(receipt)s обновлен.') % {'receipt': matched_order.receipt_number},
            )
            return redirect(
                build_redirect_url(
                    {'track': posted_track}
                )
            )

        scanned_track = _normalize_track_number(request.POST.get('track_number'))
        if not scanned_track:
            messages.warning(request, _('Введите трек-номер для поиска.'))
            return redirect(build_redirect_url())

        matched_track = find_track_match(scanned_track)
        if matched_track is None:
            messages.error(request, _('Трек %(track)s не найден в заказах.') % {'track': scanned_track})
            return redirect(build_redirect_url({'track': scanned_track}))

        matched_order = matched_track['order']
        messages.success(
            request,
            format_html(
                '{} <a href="{}" class="alert-inline-link">{}</a>',
                _('Найден заказ №%(receipt)s. Можно сразу изменить статус.') % {
                    'receipt': matched_order.receipt_number,
                },
                reverse('detail_order', args=[matched_order.slug]),
                _('Открыть'),
            ),
        )
        return redirect(build_redirect_url({'track': scanned_track}))

    selected_track_match = find_track_match(selected_track)

    arrived_qs = (
        OrderItem.objects.select_related('order')
        .only(
            'id',
            'product_name',
            'track_number',
            'order__id',
            'order__slug',
            'order__receipt_number',
            'order__first_name',
            'order__last_name',
            'order__status',
            'order__order_date',
            'order__come',
        )
        .filter(order__status=Order.Status.ARRIVED)
        .exclude(track_number__isnull=True)
        .exclude(track_number='')
    )

    if list_search:
        queue_search = Q(track_number__icontains=list_search)
        if list_search.isdigit():
            queue_search |= Q(order__receipt_number=int(list_search))
        arrived_qs = arrived_qs.filter(queue_search)

    arrived_qs = arrived_qs.order_by('-order__come', '-order__order_date', '-id')
    arrived_paginator = Paginator(arrived_qs, TRACK_QUEUE_PAGE_SIZE)
    arrived_page = arrived_paginator.get_page(request.GET.get('arrived_page'))

    return render(
        request,
        'akmalexpress/track_center.html',
        {
            'track_search_query': list_search,
            'arrived_page': arrived_page,
            'arrived_total_count': arrived_paginator.count,
            'selected_track': selected_track,
            'selected_track_match': selected_track_match,
            'status_choices': Order.Status.choices,
        },
    )


@user_passes_test(is_active_superuser)
def export_orders_excel(request):
    orders_qs = Order.objects.all()
    search_query = (request.GET.get('search') or '').strip()
    missing_track_only = parse_checkbox_flag(request.GET.get('missing_track'))
    orders_qs = apply_order_search_filter(
        orders_qs,
        search_query,
        include_phone=True,
        include_track=request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser),
    )
    orders_qs = apply_missing_track_filter(orders_qs, enabled=missing_track_only)

    selected_month = (request.GET.get('month') or '').strip()
    if request.user.is_superuser and selected_month:
        month_date = parse_month_filter(selected_month)
        if month_date:
            orders_qs = orders_qs.filter(order_date__year=month_date.year, order_date__month=month_date.month)

    orders_qs = orders_with_related(
        orders_qs
        .distinct()
        .order_by('-order_date', '-created_at')
    )
    workbook = _build_orders_workbook(orders_qs)
    return _excel_workbook_response(workbook, _build_export_filename(orders_qs))


@user_passes_test(is_active_superuser)
def import_orders_excel(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    fallback_url = reverse('orders')
    next_url = _safe_next_redirect(request, fallback_url)
    excel_file = request.FILES.get('excel_file')
    if not excel_file:
        messages.warning(request, _('Файл Excel не загружен.'))
        return redirect(next_url)

    if not excel_file.name.lower().endswith('.xlsx'):
        messages.warning(request, _('Поддерживается только формат .xlsx.'))
        return redirect(next_url)

    try:
        workbook = load_workbook(excel_file, data_only=True)
        result = _import_orders_from_workbook(workbook, acting_user=request.user, fallback_user=request.user)
    except ValueError as exc:
        messages.error(request, _('Ошибка импорта Excel: %(error)s') % {'error': exc})
        return redirect(next_url)
    except (InvalidFileException, BadZipFile, OSError):
        messages.error(request, _('Не удалось прочитать Excel файл.'))
        return redirect(next_url)

    messages.success(
        request,
        _(
            'Excel импорт завершен: создано заказов %(created)s, обновлено %(updated)s, добавлено товаров %(items)s.'
        ) % {'created': result['created_orders'], 'updated': result['updated_orders'], 'items': result['imported_items']},
    )
    if result['skipped_rows']:
        messages.warning(request, _('Пропущено строк: %(count)s.') % {'count': result['skipped_rows']})
    for row_error in result['row_errors']:
        messages.warning(request, row_error)
    return redirect(next_url)


@user_passes_test(is_active_superuser)
def dispatch_orders_view(request):
    """Dispatch board: show only new accepted orders waiting to be ordered."""

    if request.method == 'POST':
        order_id = (request.POST.get('order_id') or '').strip()
        new_status = (request.POST.get('status') or '').strip()
        available_statuses = {choice[0] for choice in Order.Status.choices}

        if order_id.isdigit() and new_status in available_statuses:
            order = get_object_or_404(Order, id=int(order_id))
            order.status = new_status
            if new_status == Order.Status.ARRIVED:
                order.come = timezone.now()
            else:
                order.come = None
            order.save(update_fields=['status', 'come', 'updated_at'])
            messages.success(request, _('Статус заказа №%(receipt)s обновлен.') % {'receipt': order.receipt_number})
        else:
            messages.warning(request, _('Не удалось обновить статус заказа.'))

        return redirect('dispatch_orders')

    dispatch_orders_base_qs = Order.objects.filter(status=Order.Status.ACCEPTED)
    dispatch_orders_qs = orders_with_related(
        dispatch_orders_base_qs.order_by('-order_date', '-created_at'),
        include_attachments=True,
    )

    total_orders = dispatch_orders_base_qs.count()
    total_items = OrderItem.objects.filter(order__status=Order.Status.ACCEPTED).count()

    paginator = Paginator(dispatch_orders_qs, 20)
    page_number = request.GET.get('page')
    try:
        orders = paginator.page(page_number)
    except PageNotAnInteger:
        orders = paginator.page(1)
    except EmptyPage:
        orders = paginator.page(paginator.num_pages)

    context = {
        'orders': orders,
        'status_choices': Order.Status.choices,
        'total_orders': total_orders,
        'total_items': total_items,
    }
    return render(request, 'akmalexpress/dispatch_orders.html', context)
