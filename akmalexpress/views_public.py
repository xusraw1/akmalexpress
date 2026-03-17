from datetime import timedelta
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import user_passes_test
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import HttpResponse, HttpResponseNotAllowed, HttpResponseNotFound, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse, translate_url
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from .context_processors import TRACK_NOTICE_DISMISS_KEY
from .i18n import normalize_language
from .models import Order
from .selectors.orders import apply_public_order_search_filter, orders_with_related
from .services.exchange_rates import get_exchange_rates
from .view_helpers import _safe_next_redirect, is_active_superuser


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
            paginator = Paginator(orders_qs, 5)
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


class ContactsView(TemplateView):
    template_name = 'akmalexpress/contacts.html'


class AboutView(TemplateView):
    """Public company information page."""
    template_name = 'akmalexpress/about.html'


class FaqView(TemplateView):
    """Public FAQ page with prohibited goods and common answers."""
    template_name = 'akmalexpress/faq.html'


contacts_view = ContactsView.as_view()
about_view = AboutView.as_view()
faq_view = FaqView.as_view()


def exchange_rates_view(request):
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
    response.set_cookie(settings.LANGUAGE_COOKIE_NAME, language, max_age=60 * 60 * 24 * 365)
    response.set_cookie('site_language', language, max_age=60 * 60 * 24 * 365)
    return response


def login_view(request):
    if request.user.is_authenticated:
        return redirect('index')

    if request.method == 'POST':
        username = (request.POST.get('username') or '').strip()
        password = request.POST.get('password') or ''
        next_url = _safe_next_redirect(request, reverse('index'), include_referer=False)
        if urlparse(next_url).path.rstrip('/') == reverse('staff_login').rstrip('/'):
            next_url = reverse('index')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            if not (user.is_staff or user.is_superuser):
                messages.error(request, _('Служебный вход доступен только администраторам.'))
                retry_url = f"{reverse('staff_login')}?{urlencode({'next': next_url})}"
                return redirect(retry_url)
            login(request, user)
            messages.success(request, _('Вы вошли в свой аккаунт'))
            return redirect(next_url)
        messages.error(request, _('Пользователь не найден, попробуйте заново'))
        retry_url = f"{reverse('staff_login')}?{urlencode({'next': next_url})}"
        return redirect(retry_url)

    return render(request, 'akmalexpress/login.html')


def logout_view(request):
    logout(request)
    messages.warning(request, _("Вы вышли из аккаунта"))
    return redirect('index')
