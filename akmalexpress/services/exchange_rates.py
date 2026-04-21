"""External exchange-rate provider integration with cache fallback chain.

Primary source is Ipak Yuli endpoint; CBU and open public APIs are used as
fallback providers. Defaults are returned only when all providers fail.
"""

import json
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from email.utils import parsedate_to_datetime
from urllib.error import URLError
from urllib.request import Request, urlopen

from django.core.cache import cache
from django.utils import timezone

CACHE_KEY = 'akmalexpress:exchange-rates:v1'
CACHE_TTL_SECONDS = 60 * 15

DEFAULT_USD_RATE = Decimal('12205.00')
DEFAULT_RMB_RATE = Decimal('1807.00')

IPAKYULI_RATE_URLS = (
    'https://wi.ipakyulibank.uz/kurs/kurs4.php',
    'http://wi.ipakyulibank.uz/kurs/kurs4.php',
)
CBU_RATES_URL = 'https://cbu.uz/uz/arkhiv-kursov-valyut/json/'
OPEN_ER_API_USD_URL = 'https://open.er-api.com/v6/latest/USD'
FRANKFURTER_USD_URL = 'https://api.frankfurter.app/latest?from=USD&to=UZS,CNY'


def _to_decimal(raw_value):
    """Parse provider value to positive Decimal(0.01) or None."""
    if raw_value in (None, ''):
        return None
    normalized = str(raw_value).strip().replace(' ', '').replace(',', '.')
    try:
        value = Decimal(normalized)
    except (InvalidOperation, TypeError, ValueError):
        return None
    if value <= 0:
        return None
    return value.quantize(Decimal('0.01'))


def _extract_three_column_rate(text, currency_code):
    # Format on ipakyuli endpoint is usually: CUR buy sell cbu
    pattern = re.compile(
        rf'\b{re.escape(currency_code)}\b[^\d]*([0-9]+(?:[.,][0-9]+)?)\s+([0-9]+(?:[.,][0-9]+)?)\s+([0-9]+(?:[.,][0-9]+)?)',
        flags=re.IGNORECASE,
    )
    match = pattern.search(text)
    if not match:
        return None
    return _to_decimal(match.group(3))


def _extract_rate_from_line(text, currency_code):
    for line in text.splitlines():
        if not re.search(rf'\b{re.escape(currency_code)}\b', line, flags=re.IGNORECASE):
            continue
        after_code = re.split(rf'\b{re.escape(currency_code)}\b', line, maxsplit=1, flags=re.IGNORECASE)[-1]
        raw_numbers = re.findall(r'([0-9]+(?:[.,][0-9]+)?)', after_code)
        for raw in reversed(raw_numbers):
            parsed = _to_decimal(raw)
            if parsed is not None:
                return parsed
    return None


def _fetch_text(url):
    """Fetch plain text payload from provider with short timeout."""
    request = Request(url, headers={'User-Agent': 'AkmalExpress/1.0'})
    with urlopen(request, timeout=6) as response:
        return response.read().decode('utf-8', errors='ignore')


def _fetch_json(url):
    request = Request(url, headers={'User-Agent': 'AkmalExpress/1.0'})
    with urlopen(request, timeout=7) as response:
        return json.loads(response.read().decode('utf-8'))


def _fetch_ipakyuli_rates():
    """Fetch USD/RMB rates from Ipak Yuli endpoint variants."""
    for url in IPAKYULI_RATE_URLS:
        try:
            body = _fetch_text(url)
        except (URLError, TimeoutError, OSError, ValueError):
            continue

        usd_rate = _extract_three_column_rate(body, 'USD') or _extract_rate_from_line(body, 'USD')
        rmb_rate = _extract_three_column_rate(body, 'CNY') or _extract_rate_from_line(body, 'CNY')
        if usd_rate is None and rmb_rate is None:
            continue
        return {
            'usd_rate': usd_rate,
            'rmb_rate': rmb_rate,
            'provider': 'ipakyuli',
            'url': url,
        }
    return {
        'usd_rate': None,
        'rmb_rate': None,
        'provider': 'ipakyuli_unavailable',
        'url': None,
    }


def _fetch_cbu_rates():
    """Fetch USD/RMB rates from CBU JSON archive endpoint."""
    request = Request(CBU_RATES_URL, headers={'User-Agent': 'AkmalExpress/1.0'})
    with urlopen(request, timeout=6) as response:
        payload = json.loads(response.read().decode('utf-8'))

    usd_rate = None
    rmb_rate = None
    updated_on = None

    if isinstance(payload, list):
        for item in payload:
            if not isinstance(item, dict):
                continue
            ccy = str(item.get('Ccy') or '').upper()
            if ccy == 'USD' and usd_rate is None:
                usd_rate = _to_decimal(item.get('Rate'))
                updated_on = str(item.get('Date') or updated_on or '')
            elif ccy == 'CNY' and rmb_rate is None:
                rmb_rate = _to_decimal(item.get('Rate'))
                updated_on = str(item.get('Date') or updated_on or '')
            if usd_rate is not None and rmb_rate is not None:
                break

    return {
        'usd_rate': usd_rate,
        'rmb_rate': rmb_rate,
        'provider': 'cbu',
        'url': CBU_RATES_URL,
        'updated_on': updated_on,
    }


def _format_iso_date_for_ui(raw_value):
    text = str(raw_value or '').strip()
    if not text:
        return ''
    try:
        parsed_email_date = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        parsed_email_date = None
    if parsed_email_date is not None:
        return parsed_email_date.strftime('%d.%m.%Y')
    for fmt in ('%Y-%m-%d', '%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%d %H:%M:%S'):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.strftime('%d.%m.%Y')
        except ValueError:
            continue
    return ''


def _derive_cny_to_uzs_rate(usd_to_uzs, usd_to_cny):
    if usd_to_uzs is None or usd_to_cny is None or usd_to_cny <= 0:
        return None
    try:
        return (usd_to_uzs / usd_to_cny).quantize(Decimal('0.01'))
    except (InvalidOperation, ZeroDivisionError):
        return None


def _fetch_open_er_api_rates():
    payload = _fetch_json(OPEN_ER_API_USD_URL)
    if not isinstance(payload, dict):
        return {
            'usd_rate': None,
            'rmb_rate': None,
            'provider': 'open_er_api_unavailable',
            'url': OPEN_ER_API_USD_URL,
            'updated_on': '',
        }

    rates = payload.get('rates')
    if not isinstance(rates, dict):
        return {
            'usd_rate': None,
            'rmb_rate': None,
            'provider': 'open_er_api_unavailable',
            'url': OPEN_ER_API_USD_URL,
            'updated_on': '',
        }

    usd_rate = _to_decimal(rates.get('UZS'))
    usd_to_cny = _to_decimal(rates.get('CNY'))
    rmb_rate = _derive_cny_to_uzs_rate(usd_rate, usd_to_cny)
    updated_on = _format_iso_date_for_ui(payload.get('time_last_update_utc'))

    return {
        'usd_rate': usd_rate,
        'rmb_rate': rmb_rate,
        'provider': 'open_er_api',
        'url': OPEN_ER_API_USD_URL,
        'updated_on': updated_on,
    }


def _fetch_frankfurter_rates():
    payload = _fetch_json(FRANKFURTER_USD_URL)
    if not isinstance(payload, dict):
        return {
            'usd_rate': None,
            'rmb_rate': None,
            'provider': 'frankfurter_unavailable',
            'url': FRANKFURTER_USD_URL,
            'updated_on': '',
        }

    rates = payload.get('rates')
    if not isinstance(rates, dict):
        return {
            'usd_rate': None,
            'rmb_rate': None,
            'provider': 'frankfurter_unavailable',
            'url': FRANKFURTER_USD_URL,
            'updated_on': '',
        }

    usd_rate = _to_decimal(rates.get('UZS'))
    usd_to_cny = _to_decimal(rates.get('CNY'))
    rmb_rate = _derive_cny_to_uzs_rate(usd_rate, usd_to_cny)
    updated_on = _format_iso_date_for_ui(payload.get('date'))

    return {
        'usd_rate': usd_rate,
        'rmb_rate': rmb_rate,
        'provider': 'frankfurter',
        'url': FRANKFURTER_USD_URL,
        'updated_on': updated_on,
    }


def _resolve_rate_with_source(*providers, field):
    for provider in providers:
        value = provider.get(field)
        if value is not None:
            return value, provider.get('provider')
    return None, None


def _source_label_for_currency(provider_name, currency_code):
    mapping = {
        'ipakyuli': f'{currency_code}:Ipakyuli',
        'cbu': f'{currency_code}:CBU',
        'open_er_api': f'{currency_code}:OpenERAPI',
        'frankfurter': f'{currency_code}:Frankfurter',
    }
    return mapping.get(provider_name, f'{currency_code}:default')


def get_exchange_rates(force_refresh=False):
    """Return normalized exchange rates payload for UI/API consumption."""
    if not force_refresh:
        cached = cache.get(CACHE_KEY)
        if isinstance(cached, dict):
            return cached

    ipakyuli_data = _fetch_ipakyuli_rates()

    cbu_data = {
        'usd_rate': None,
        'rmb_rate': None,
        'provider': 'cbu_unavailable',
        'url': CBU_RATES_URL,
        'updated_on': '',
    }
    open_er_api_data = {
        'usd_rate': None,
        'rmb_rate': None,
        'provider': 'open_er_api_unavailable',
        'url': OPEN_ER_API_USD_URL,
        'updated_on': '',
    }
    frankfurter_data = {
        'usd_rate': None,
        'rmb_rate': None,
        'provider': 'frankfurter_unavailable',
        'url': FRANKFURTER_USD_URL,
        'updated_on': '',
    }
    try:
        cbu_data = _fetch_cbu_rates()
    except (URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError):
        pass
    try:
        open_er_api_data = _fetch_open_er_api_rates()
    except (URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError):
        pass
    try:
        frankfurter_data = _fetch_frankfurter_rates()
    except (URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError):
        pass
    providers_chain = (ipakyuli_data, cbu_data, open_er_api_data, frankfurter_data)

    usd_rate, usd_provider = _resolve_rate_with_source(*providers_chain, field='usd_rate')
    rmb_rate, rmb_provider = _resolve_rate_with_source(*providers_chain, field='rmb_rate')
    usd_rate = usd_rate or DEFAULT_USD_RATE
    rmb_rate = rmb_rate or DEFAULT_RMB_RATE

    source_parts = [
        _source_label_for_currency(usd_provider, 'USD'),
        _source_label_for_currency(rmb_provider, 'RMB'),
    ]

    source_date = ''
    for provider in providers_chain:
        updated = str(provider.get('updated_on') or '').strip()
        if updated:
            source_date = updated
            break
    if not source_date:
        source_date = timezone.localdate().strftime('%d.%m.%Y')

    result = {
        'usd_rate': f'{usd_rate:.2f}',
        'rmb_rate': f'{rmb_rate:.2f}',
        'source': ', '.join(source_parts),
        'source_date': source_date,
        'fetched_at': timezone.now().isoformat(),
    }
    cache.set(CACHE_KEY, result, CACHE_TTL_SECONDS)
    return result
