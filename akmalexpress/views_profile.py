"""Profile views for admins/staff with inline edit and filtered order history."""

from decimal import Decimal
from zipfile import BadZipFile

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import HttpResponseNotAllowed, JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from .models import Order, UserProfile
from .i18n import translate_html_content
from .selectors.orders import apply_missing_track_filter, apply_order_search_filter, orders_with_related, parse_checkbox_flag
from .services.excel import (
    _build_export_filename,
    _build_orders_workbook,
    _excel_workbook_response,
    _import_orders_from_workbook,
)
from .services.images import optimize_uploaded_image
from .view_helpers import (
    PROFILE_PERIOD_OPTIONS,
    PROFILE_STATUS_FILTER_MAP,
    PROFILE_STATUS_OPTIONS,
    _get_or_create_user_profile,
    _resolve_profile_period,
    _safe_next_redirect,
    is_active_superuser,
)

PROFILE_ORDERS_PAGE_SIZE = 10


@user_passes_test(is_active_superuser)
def my_profile_redirect(request):
    """Redirect `/profile/` to canonical username-based profile URL."""
    target_url = reverse('profile', kwargs={'user': request.user.username})
    query = request.GET.urlencode()
    if query:
        target_url = f'{target_url}?{query}'
    return redirect(target_url)


def _resolve_profile_user(user):
    """Resolve user by username (case-insensitive, optional leading `@`)."""
    normalized_user = (user or '').strip().lstrip('@')
    if not normalized_user:
        return None
    return User.objects.filter(username__iexact=normalized_user).first()


def _apply_profile_orders_filters(queryset, request_user, search, status_filter, date_from, date_to, missing_track_only=False):
    """Apply profile order filters shared by page view and Excel export."""
    queryset = apply_order_search_filter(
        queryset,
        search,
        include_track=request_user.is_authenticated and (request_user.is_staff or request_user.is_superuser),
    )
    queryset = apply_missing_track_filter(queryset, enabled=missing_track_only)

    status_codes = PROFILE_STATUS_FILTER_MAP.get(status_filter)
    if status_codes:
        queryset = queryset.filter(status__in=status_codes)

    if date_from:
        queryset = queryset.filter(order_date__gte=date_from)
    if date_to:
        queryset = queryset.filter(order_date__lte=date_to)

    return queryset


@user_passes_test(is_active_superuser)
def profile_view(request, user):
    """Admin profile page with inline editing and AJAX filters over user's orders."""
    profile = _resolve_profile_user(user)
    if profile is None:
        messages.error(request, _('Пользователь не найден'))
        return redirect('index')

    if not (profile.is_superuser or profile.is_staff or profile.is_active):
        messages.warning(request, _('Вы не имеете доступ к этому профилю'))
        return redirect('index')

    allowed_sorts = {
        'date_desc': ('-order_date', '-created_at'),
        'date_asc': ('order_date', 'created_at'),
        'receipt_desc': ('-receipt_number', '-created_at'),
        'receipt_asc': ('receipt_number', 'created_at'),
        'status_asc': ('status', '-order_date'),
        'status_desc': ('-status', '-order_date'),
    }
    sort_labels = {
        'date_desc': _('Дата (новые)'),
        'date_asc': _('Дата (старые)'),
        'receipt_desc': _('Квитанция (по убыванию)'),
        'receipt_asc': _('Квитанция (по возрастанию)'),
        'status_asc': _('Статус (А-Я)'),
        'status_desc': _('Статус (Я-А)'),
    }

    can_edit_profile = request.user.is_superuser or request.user == profile
    user_profile = UserProfile.objects.filter(user=profile).first()

    if request.method == 'POST' and request.POST.get('action') == 'update_profile':
        if not can_edit_profile:
            messages.error(request, _('У вас нет прав для редактирования этого профиля.'))
            return redirect('profile', user=profile.username)

        first_name = (request.POST.get('first_name') or '').strip()
        last_name = (request.POST.get('last_name') or '').strip()
        username = (request.POST.get('username') or '').strip().lstrip('@')
        remove_avatar = request.POST.get('remove_avatar') == '1'
        avatar_file = request.FILES.get('avatar')
        current_password = request.POST.get('current_password') or ''
        new_password = request.POST.get('new_password') or ''
        confirm_password = request.POST.get('confirm_password') or ''

        if not first_name:
            messages.warning(request, _('Укажите имя.'))
            return redirect('profile', user=profile.username)
        if not last_name:
            messages.warning(request, _('Укажите фамилию.'))
            return redirect('profile', user=profile.username)
        if not username:
            messages.warning(request, _('Укажите логин.'))
            return redirect('profile', user=profile.username)
        if len(username) < 3:
            messages.warning(request, _('Логин должен содержать минимум 3 символа.'))
            return redirect('profile', user=profile.username)
        username_taken = User.objects.filter(username__iexact=username).exclude(id=profile.id).exists()
        if username_taken:
            messages.warning(request, _('Пользователь с таким логином уже существует.'))
            return redirect('profile', user=profile.username)

        password_change_requested = bool(new_password or confirm_password)
        if password_change_requested:
            if new_password != confirm_password:
                messages.warning(request, _('Новый пароль и подтверждение не совпадают.'))
                return redirect('profile', user=profile.username)
            if len(new_password) < 6:
                messages.warning(request, _('Пароль должен содержать минимум 6 символов.'))
                return redirect('profile', user=profile.username)
            is_self_edit = request.user == profile
            if is_self_edit and not request.user.is_superuser and not profile.check_password(current_password):
                messages.warning(request, _('Введите текущий пароль для изменения пароля.'))
                return redirect('profile', user=profile.username)

        if avatar_file:
            content_type = (getattr(avatar_file, 'content_type', '') or '').lower()
            file_size = getattr(avatar_file, 'size', 0) or 0
            if content_type and not content_type.startswith('image/'):
                messages.warning(request, _('Можно загружать только изображения.'))
                return redirect('profile', user=profile.username)
            if file_size > 5 * 1024 * 1024:
                messages.warning(request, _('Размер фото профиля не должен превышать 5MB.'))
                return redirect('profile', user=profile.username)

        old_username = profile.username
        profile.first_name = first_name[:150]
        profile.last_name = last_name[:150]
        profile.username = username[:150]
        update_fields = ['first_name', 'last_name', 'username']
        if password_change_requested:
            profile.set_password(new_password)
            update_fields.append('password')
        profile.save(update_fields=update_fields)
        if request.user == profile and password_change_requested:
            update_session_auth_hash(request, profile)

        user_profile = user_profile or _get_or_create_user_profile(profile)
        if remove_avatar and user_profile.avatar:
            user_profile.avatar.delete(save=False)
            user_profile.avatar = None
        if avatar_file:
            user_profile.avatar = optimize_uploaded_image(avatar_file, max_size=(600, 600), quality=86)
        user_profile.save()

        messages.success(request, _('Профиль успешно обновлен.'))
        target_username = profile.username or old_username
        return redirect('profile', user=target_username)

    search = (request.GET.get('search') or '').strip()
    status_filter = (request.GET.get('status') or 'all').strip()
    period_filter = (request.GET.get('period') or 'all').strip()
    date_from_raw = (request.GET.get('date_from') or '').strip()
    date_to_raw = (request.GET.get('date_to') or '').strip()
    sort = (request.GET.get('sort') or 'date_desc').strip()
    missing_track_only = parse_checkbox_flag(request.GET.get('missing_track'))

    if status_filter not in {key for key, _ in PROFILE_STATUS_OPTIONS}:
        status_filter = 'all'
    if sort not in allowed_sorts:
        sort = 'date_desc'

    period_filter, date_from, date_to, period_errors = _resolve_profile_period(
        period=period_filter,
        date_from_raw=date_from_raw,
        date_to_raw=date_to_raw,
    )
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        for error_text in period_errors:
            messages.warning(request, error_text)

    base_profile_orders_qs = Order.objects.filter(user=profile)
    all_profile_orders_qs = orders_with_related(
        base_profile_orders_qs.order_by('-order_date', '-created_at')
    )
    profile_total_amount = sum((o.get_final_total for o in all_profile_orders_qs), Decimal('0.00'))
    orders_total_count = base_profile_orders_qs.count()

    profile_orders_qs = _apply_profile_orders_filters(
        queryset=base_profile_orders_qs,
        request_user=request.user,
        search=search,
        status_filter=status_filter,
        date_from=date_from,
        date_to=date_to,
        missing_track_only=missing_track_only,
    )
    profile_orders_qs = orders_with_related(profile_orders_qs.distinct().order_by(*allowed_sorts[sort]))
    filtered_total_amount = sum((o.get_final_total for o in profile_orders_qs), Decimal('0.00'))

    paginator = Paginator(profile_orders_qs, PROFILE_ORDERS_PAGE_SIZE)
    page_number = request.GET.get('page')

    try:
        orders = paginator.page(page_number)
    except PageNotAnInteger:
        orders = paginator.page(1)
    except EmptyPage:
        orders = paginator.page(paginator.num_pages)

    orders_partial_context = {
        'profile': profile,
        'orders': orders,
        'orders_total_count': orders_total_count,
        'filtered_total_amount': filtered_total_amount,
        'filters': {
            'search': search,
            'status': status_filter,
            'period': period_filter,
            'date_from': date_from.strftime('%Y-%m-%d') if date_from else '',
            'date_to': date_to.strftime('%Y-%m-%d') if date_to else '',
            'sort': sort,
            'sort_label': sort_labels.get(sort, sort_labels['date_desc']),
            'missing_track': missing_track_only,
        },
        'profile_status_options': PROFILE_STATUS_OPTIONS,
        'profile_period_options': PROFILE_PERIOD_OPTIONS,
        'profile_sort_options': list(sort_labels.items()),
    }

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        html = render_to_string(
            'akmalexpress/partials/profile_orders_section.html',
            orders_partial_context,
            request=request,
        )
        if str(getattr(request, 'LANGUAGE_CODE', '')).startswith('uz'):
            html = translate_html_content(html, 'uz')
        return JsonResponse({'html': html})

    return render(
        request,
        'akmalexpress/profile.html',
        {
            'profile': profile,
            'profile_total_amount': profile_total_amount,
            'orders_total_count': orders_total_count,
            'orders': orders,
            'filtered_total_amount': filtered_total_amount,
            'filters': orders_partial_context['filters'],
            'profile_status_options': PROFILE_STATUS_OPTIONS,
            'profile_period_options': PROFILE_PERIOD_OPTIONS,
            'profile_sort_options': list(sort_labels.items()),
            'user_profile': user_profile,
            'can_edit_profile': can_edit_profile,
            'orders_partial_context': orders_partial_context,
        },
    )


@user_passes_test(is_active_superuser)
def export_profile_orders_excel(request, user):
    """Export filtered profile orders into formatted XLSX report."""
    profile = _resolve_profile_user(user)
    if profile is None:
        messages.error(request, _('Пользователь не найден'))
        return redirect('index')

    allowed_sorts = {
        'date_desc': ('-order_date', '-created_at'),
        'date_asc': ('order_date', 'created_at'),
        'receipt_desc': ('-receipt_number', '-created_at'),
        'receipt_asc': ('receipt_number', 'created_at'),
        'status_asc': ('status', '-order_date'),
        'status_desc': ('-status', '-order_date'),
    }

    search = (request.GET.get('search') or '').strip()
    status_filter = (request.GET.get('status') or 'all').strip()
    period_filter = (request.GET.get('period') or 'all').strip()
    date_from_raw = (request.GET.get('date_from') or '').strip()
    date_to_raw = (request.GET.get('date_to') or '').strip()
    sort = (request.GET.get('sort') or 'date_desc').strip()
    missing_track_only = parse_checkbox_flag(request.GET.get('missing_track'))

    if status_filter not in {key for key, _ in PROFILE_STATUS_OPTIONS}:
        status_filter = 'all'
    if sort not in allowed_sorts:
        sort = 'date_desc'

    _, date_from, date_to, _ = _resolve_profile_period(
        period=period_filter,
        date_from_raw=date_from_raw,
        date_to_raw=date_to_raw,
    )

    orders_qs = _apply_profile_orders_filters(
        queryset=Order.objects.filter(user=profile),
        request_user=request.user,
        search=search,
        status_filter=status_filter,
        date_from=date_from,
        date_to=date_to,
        missing_track_only=missing_track_only,
    )

    orders_qs = orders_with_related(orders_qs.distinct().order_by(*allowed_sorts[sort]))
    workbook = _build_orders_workbook(orders_qs)
    return _excel_workbook_response(workbook, _build_export_filename(orders_qs))


@user_passes_test(is_active_superuser)
def import_profile_orders_excel(request, user):
    """Import orders from XLSX into profile context preserving business rules."""
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    profile = _resolve_profile_user(user)
    if profile is None:
        messages.error(request, _('Пользователь не найден'))
        return redirect('index')

    fallback_url = reverse('profile', kwargs={'user': profile.username})
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
        result = _import_orders_from_workbook(workbook, acting_user=request.user, fallback_user=profile)
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
