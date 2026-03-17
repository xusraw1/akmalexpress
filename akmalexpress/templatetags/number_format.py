from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django import template

register = template.Library()


@register.filter
def money(value, precision=2):
    """Format numeric values using spaces as thousands separators."""
    if value in (None, ''):
        return ''

    try:
        decimals = int(precision)
    except (TypeError, ValueError):
        decimals = 2

    decimals = max(decimals, 0)

    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return value

    if decimals == 0:
        rounded = number.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        return f'{rounded:,.0f}'.replace(',', ' ')

    quant = Decimal('1').scaleb(-decimals)
    rounded = number.quantize(quant, rounding=ROUND_HALF_UP)
    formatted = f'{rounded:,.{decimals}f}'.replace(',', ' ')
    return formatted.rstrip('0').rstrip('.')
