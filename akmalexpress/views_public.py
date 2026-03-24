"""Public-facing views: search, static pages, auth entry, language switch."""

import hashlib
from datetime import timedelta
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import user_passes_test
from django.core.cache import cache
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import HttpResponse, HttpResponseNotAllowed, HttpResponseNotFound, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse, translate_url
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from .context_processors import TRACK_NOTICE_DISMISS_KEY
from .forms import ContactRequestForm
from .i18n import normalize_language
from .models import Order
from .selectors.orders import apply_public_order_search_filter, orders_with_related
from .services.exchange_rates import get_exchange_rates
from .services.telegram import send_contact_request_notification
from .view_helpers import _safe_next_redirect, is_active_superuser

PUBLIC_SEARCH_PAGE_SIZE = 10


def _staff_login_client_ip(request):
    """Resolve best-effort client IP from proxy headers for rate limiting."""
    cf_ip = (request.META.get('HTTP_CF_CONNECTING_IP') or '').strip()
    if cf_ip:
        return cf_ip

    forwarded = (request.META.get('HTTP_X_FORWARDED_FOR') or '').strip()
    if forwarded:
        return forwarded.split(',')[0].strip()

    return (request.META.get('REMOTE_ADDR') or '').strip() or 'unknown'


def _staff_login_limit_keys(request, username):
    """Return cache keys for both IP-only and IP+username lock dimensions."""
    client_ip = _staff_login_client_ip(request)
    normalized_username = (username or '').strip().lower() or 'anonymous'
    ip_hash = hashlib.sha256(f"ip|{client_ip}".encode('utf-8')).hexdigest()[:24]
    combo_hash = hashlib.sha256(f"ip_user|{client_ip}|{normalized_username}".encode('utf-8')).hexdigest()[:24]
    return (
        (f'staff_login:fail:{ip_hash}', f'staff_login:lock:{ip_hash}'),
        (f'staff_login:fail:{combo_hash}', f'staff_login:lock:{combo_hash}'),
    )


def _staff_login_lock_seconds_left(request, username):
    """Return current lock TTL for this request/user tuple (0 if unlocked)."""
    now_ts = timezone.now().timestamp()
    max_left = 0
    for _fail_key, lock_key in _staff_login_limit_keys(request, username):
        lock_until = cache.get(lock_key)
        if not lock_until:
            continue
        try:
            seconds_left = int(float(lock_until) - now_ts)
        except (TypeError, ValueError):
            cache.delete(lock_key)
            continue
        if seconds_left <= 0:
            cache.delete(lock_key)
            continue
        max_left = max(max_left, seconds_left)
    return max_left


def _staff_login_register_failure(request, username):
    """Increase failure counters and create temporary lock when threshold is hit."""
    attempts_limit = int(getattr(settings, 'STAFF_LOGIN_RATE_LIMIT_ATTEMPTS', 8))
    window_seconds = int(getattr(settings, 'STAFF_LOGIN_RATE_LIMIT_WINDOW_SECONDS', 900))
    lock_seconds = int(getattr(settings, 'STAFF_LOGIN_RATE_LIMIT_LOCK_SECONDS', 900))

    should_lock = False
    for fail_key, _lock_key in _staff_login_limit_keys(request, username):
        current = cache.get(fail_key)
        try:
            current_count = int(current or 0)
        except (TypeError, ValueError):
            current_count = 0
        current_count += 1
        cache.set(fail_key, current_count, timeout=window_seconds)
        if current_count >= attempts_limit:
            should_lock = True

    if should_lock:
        lock_until = timezone.now().timestamp() + lock_seconds
        for fail_key, lock_key in _staff_login_limit_keys(request, username):
            cache.set(lock_key, lock_until, timeout=lock_seconds)
            cache.delete(fail_key)
        return lock_seconds
    return 0


def _staff_login_clear_failure_state(request, username):
    """Drop all lock/failure keys after successful authentication."""
    for fail_key, lock_key in _staff_login_limit_keys(request, username):
        cache.delete(fail_key)
        cache.delete(lock_key)


def index(request):
    """Global order search page with exact matching by receipt/FIO/phone/track."""
    context = {}
    search = (request.GET.get('search') or '').strip()

    context['search_query'] = search
    has_filters = bool(search)
    if has_filters:
        queryset = Order.objects.all()
        queryset = apply_public_order_search_filter(queryset, search)

        orders_qs = orders_with_related(
            queryset
            .distinct()
            .order_by('-order_date', '-created_at')
        )

        if orders_qs.exists():
            paginator = Paginator(orders_qs, PUBLIC_SEARCH_PAGE_SIZE)
            page_number = request.GET.get('page')

            try:
                orders = paginator.page(page_number)
            except PageNotAnInteger:
                orders = paginator.page(1)
            except EmptyPage:
                orders = paginator.page(paginator.num_pages)

            if search and not page_number:
                messages.success(request, _("Заказы по вашему запросу '%(query)s' найдены") % {'query': search})
            context['orders'] = orders
        else:
            messages.info(request, _("По вашему запросу '%(query)s' ничего не найдено") % {'query': search})

    return render(request, 'index.html', context)


def contacts_view(request):
    """Render contacts page and process lightweight callback requests."""
    contact_form = ContactRequestForm(request.POST or None)
    if request.method == 'POST':
        if contact_form.is_valid():
            cleaned = contact_form.cleaned_data
            telegram_sent = send_contact_request_notification(
                name=cleaned['name'],
                phone=cleaned['phone'],
                email=cleaned['email'],
                message=cleaned['message'],
                page_url=request.build_absolute_uri(request.path),
            )
            messages.success(request, _('Запрос отправлен. Мы свяжемся с вами в ближайшее время.'))
            if not telegram_sent:
                messages.warning(request, _('Не удалось отправить уведомление в Telegram. Проверьте настройки бота.'))
            return redirect('contacts')
        messages.warning(request, _('Проверьте форму: заполните все поля корректно.'))
    return render(request, 'akmalexpress/contacts.html', {'contact_form': contact_form})


class AboutView(TemplateView):
    """Public company information page."""
    template_name = 'akmalexpress/about.html'


class FaqView(TemplateView):
    """Public FAQ page with prohibited goods and common answers."""
    template_name = 'akmalexpress/faq.html'


about_view = AboutView.as_view()
faq_view = FaqView.as_view()


def exchange_rates_view(request):
    """Expose exchange rates to frontend auto-fill widgets."""
    if request.method != 'GET':
        return HttpResponseNotAllowed(['GET'])
    return JsonResponse(get_exchange_rates())


def hidden_entrypoint(request):
    """Return 404 for legacy public URLs that should stay hidden."""
    return HttpResponseNotFound('Not found')


def panel_entrypoint(request):
    """Unified convenience entrypoint for staff/superusers."""
    if not request.user.is_authenticated:
        return redirect('staff_login')
    if request.user.is_superuser:
        return redirect(f"/{settings.ADMIN_URL}")
    if request.user.is_staff:
        return redirect('orders')
    return redirect('index')


def custom_404(request, exception):
    """Render branded 404 page for unknown routes."""
    return render(request, '404.html', status=404)


def custom_404_debug(request, unmatched_path=''):
    """Render 404 page for debug mode catch-all route."""
    return render(request, '404.html', status=404)


@user_passes_test(is_active_superuser)
def dismiss_track_notice(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    dismissed_until = timezone.now() + timedelta(days=2)
    request.session[TRACK_NOTICE_DISMISS_KEY] = dismissed_until.isoformat()

    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or '/'
    if not url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        next_url = '/'

    messages.info(request, _('Напоминание о трек-номерах скрыто на 2 дня.'))
    return redirect(next_url)


def robots_txt(request):
    """Block indexing of private/admin pages for search crawlers."""
    admin_path = f"/{settings.ADMIN_URL}".replace('//', '/')
    staff_login_path = f"/{settings.STAFF_LOGIN_URL}".replace('//', '/')
    private_paths = list(dict.fromkeys([
        admin_path,
        admin_path.rstrip('/'),
        staff_login_path,
        staff_login_path.rstrip('/'),
        '/login/',
        '/logout/',
        '/panel/',
        '/panel',
        '/notifications/',
        '/order/',
        '/create/',
        '/toggle_status/',
        '/delete_admin/',
        '/profile/',
    ]))
    lines = ['User-agent: *']
    lines.extend(f'Disallow: {path}' for path in private_paths)
    lines.append('')
    return HttpResponse('\n'.join(lines), content_type='text/plain')


def set_language_view(request, lang_code):
    """Switch language and safely redirect back to previous local URL."""
    language = normalize_language(lang_code)
    request.session[settings.LANGUAGE_COOKIE_NAME] = language
    request.session['site_language'] = language

    next_url = request.GET.get('next') or request.META.get('HTTP_REFERER') or '/'
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        next_url = '/'
    else:
        parsed_next = urlparse(next_url)
        clean_query = [(key, value) for key, value in parse_qsl(parsed_next.query, keep_blank_values=True) if key != 'lang']
        cleaned_path = parsed_next.path or '/'
        if cleaned_path == '/ru':
            cleaned_path = '/'
        elif cleaned_path.startswith('/ru/'):
            cleaned_path = f"/{cleaned_path.removeprefix('/ru/')}"

        if language == 'ru':
            if cleaned_path == '/uz':
                cleaned_path = '/'
            elif cleaned_path.startswith('/uz/'):
                cleaned_path = f"/{cleaned_path.removeprefix('/uz/')}"

        sanitized_url = urlunparse(
            parsed_next._replace(
                path=cleaned_path,
                query=urlencode(clean_query, doseq=True),
            )
        )

        if language == 'ru':
            candidate_url = sanitized_url
        else:
            candidate_url = translate_url(sanitized_url, language) or sanitized_url

        if url_has_allowed_host_and_scheme(
            candidate_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            next_url = candidate_url
        else:
            next_url = '/'

    response = redirect(next_url)
    cookie_kwargs = {
        'max_age': 60 * 60 * 24 * 365,
        'secure': getattr(settings, 'LANGUAGE_COOKIE_SECURE', False),
        'httponly': getattr(settings, 'LANGUAGE_COOKIE_HTTPONLY', False),
        'samesite': getattr(settings, 'LANGUAGE_COOKIE_SAMESITE', 'Lax'),
    }
    response.set_cookie(settings.LANGUAGE_COOKIE_NAME, language, **cookie_kwargs)
    response.set_cookie('site_language', language, **cookie_kwargs)
    return response


def login_view(request):
    """Staff login endpoint with cache-based brute-force throttling."""
    if request.user.is_authenticated:
        return redirect('index')

    if request.method == 'POST':
        username = (request.POST.get('username') or '').strip()
        password = request.POST.get('password') or ''
        next_url = _safe_next_redirect(request, reverse('index'), include_referer=False)
        if urlparse(next_url).path.rstrip('/') == reverse('staff_login').rstrip('/'):
            next_url = reverse('index')
        retry_url = f"{reverse('staff_login')}?{urlencode({'next': next_url})}"

        lock_seconds_left = _staff_login_lock_seconds_left(request, username)
        if lock_seconds_left > 0:
            messages.error(
                request,
                _('Слишком много попыток входа. Повторите через %(seconds)s сек.') % {'seconds': lock_seconds_left},
            )
            return redirect(retry_url)

        user = authenticate(request, username=username, password=password)
        if user is not None:
            if not (user.is_staff or user.is_superuser):
                lock_after_failure = _staff_login_register_failure(request, username)
                if lock_after_failure > 0:
                    messages.error(
                        request,
                        _('Слишком много попыток входа. Повторите через %(seconds)s сек.') % {
                            'seconds': lock_after_failure,
                        },
                    )
                    return redirect(retry_url)
                messages.error(request, _('Служебный вход доступен только администраторам.'))
                return redirect(retry_url)
            login(request, user)
            _staff_login_clear_failure_state(request, username)
            messages.success(request, _('Вы вошли в свой аккаунт'))
            return redirect(next_url)

        lock_after_failure = _staff_login_register_failure(request, username)
        if lock_after_failure > 0:
            messages.error(
                request,
                _('Слишком много попыток входа. Повторите через %(seconds)s сек.') % {'seconds': lock_after_failure},
            )
            return redirect(retry_url)
        messages.error(request, _('Пользователь не найден, попробуйте заново'))
        return redirect(retry_url)

    return render(request, 'akmalexpress/login.html')


def logout_view(request):
    logout(request)
    messages.warning(request, _("Вы вышли из аккаунта"))
    return redirect('index')
