from django import template


register = template.Library()


@register.simple_tag
def compact_page_tokens(page_obj, edge=2, around=1):
    """Return compact pagination tokens with ellipsis markers (None)."""
    if not page_obj:
        return []

    total = page_obj.paginator.num_pages
    current = page_obj.number

    pages = set()
    for page in range(1, min(edge, total) + 1):
        pages.add(page)
    for page in range(max(1, total - edge + 1), total + 1):
        pages.add(page)
    for page in range(max(1, current - around), min(total, current + around) + 1):
        pages.add(page)

    ordered_pages = sorted(pages)
    tokens = []
    previous = None
    for page in ordered_pages:
        if previous is not None and page - previous > 1:
            tokens.append(None)
        tokens.append(page)
        previous = page
    return tokens

