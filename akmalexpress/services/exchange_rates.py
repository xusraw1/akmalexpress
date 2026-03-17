import json
import re
from decimal import Decimal, InvalidOperation
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


def _to_decimal(raw_value):
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
    request = Request(url, headers={'User-Agent': 'AkmalExpress/1.0'})
    with urlopen(request, timeout=6) as response:
        return response.read().decode('utf-8', errors='ignore')


def _fetch_ipakyuli_rates():
    for url in IPAKYULI_RATE_URLS:
        try:
            body = _fetch_text(url)
        except Exception:
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


def get_exchange_rates(force_refresh=False):
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
    try:
        cbu_data = _fetch_cbu_rates()
    except (URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError):
        pass

    usd_rate = ipakyuli_data['usd_rate'] or cbu_data['usd_rate'] or DEFAULT_USD_RATE
    rmb_rate = ipakyuli_data['rmb_rate'] or cbu_data['rmb_rate'] or DEFAULT_RMB_RATE

    source_parts = []
    if ipakyuli_data['usd_rate'] is not None:
        source_parts.append('USD:Ipakyuli')
    elif cbu_data['usd_rate'] is not None:
        source_parts.append('USD:CBU')
    else:
        source_parts.append('USD:default')

    if ipakyuli_data['rmb_rate'] is not None:
        source_parts.append('RMB:Ipakyuli')
    elif cbu_data['rmb_rate'] is not None:
        source_parts.append('RMB:CBU')
    else:
        source_parts.append('RMB:default')

    result = {
        'usd_rate': f'{usd_rate:.2f}',
        'rmb_rate': f'{rmb_rate:.2f}',
        'source': ', '.join(source_parts),
        'source_date': cbu_data.get('updated_on') or timezone.localdate().strftime('%d.%m.%Y'),
        'fetched_at': timezone.now().isoformat(),
    }
    cache.set(CACHE_KEY, result, CACHE_TTL_SECONDS)
    return result
