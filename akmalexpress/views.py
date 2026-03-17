"""Backward-compatible view exports.

This module keeps the public import surface stable while actual view
implementations live in focused modules:
- views_public.py
- views_orders.py
- views_profile.py
- views_admins.py
"""

from .views_admins import create_admin, delete_admin, toggle_status
from .views_orders import (
    change_order,
    create_order,
    create_product,
    delete_order,
    detail_order,
    dispatch_orders_view,
    export_orders_excel,
    import_orders_excel,
    order_list,
    order_total_preview,
    print_settlement_sheet,
    print_receipt,
    track_center_view,
)
from .views_profile import (
    export_profile_orders_excel,
    import_profile_orders_excel,
    my_profile_redirect,
    profile_view,
)
from .views_public import (
    about_view,
    contacts_view,
    custom_404,
    custom_404_debug,
    dismiss_track_notice,
    exchange_rates_view,
    faq_view,
    hidden_entrypoint,
    index,
    login_view,
    logout_view,
    panel_entrypoint,
    robots_txt,
    set_language_view,
)

__all__ = [
    'about_view',
    'change_order',
    'contacts_view',
    'create_admin',
    'create_order',
    'create_product',
    'custom_404',
    'custom_404_debug',
    'delete_admin',
    'delete_order',
    'detail_order',
    'dismiss_track_notice',
    'dispatch_orders_view',
    'exchange_rates_view',
    'export_orders_excel',
    'export_profile_orders_excel',
    'faq_view',
    'hidden_entrypoint',
    'import_orders_excel',
    'import_profile_orders_excel',
    'index',
    'login_view',
    'logout_view',
    'my_profile_redirect',
    'order_list',
    'order_total_preview',
    'panel_entrypoint',
    'print_settlement_sheet',
    'print_receipt',
    'profile_view',
    'robots_txt',
    'set_language_view',
    'track_center_view',
    'toggle_status',
]
