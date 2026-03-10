from io import BytesIO
from decimal import Decimal
from openpyxl import Workbook, load_workbook

from django.contrib.auth.models import User
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from datetime import timedelta
from django.utils.crypto import get_random_string
from django.utils import timezone

from .context_processors import TRACK_NOTICE_DISMISS_KEY
from .models import Order, OrderAttachment, OrderItem
from .templatetags.number_format import money


class ProfileViewTests(TestCase):
    def setUp(self):
        test_password = get_random_string(24)
        self.staff = User.objects.create_user(
            username='profileadmin',
            password=test_password,
            is_staff=True,
            is_active=True,
        )
        self.client.login(username='profileadmin', password=test_password)

        order = Order.objects.create(
            user=self.staff,
            receipt_number=123,
            order_date=timezone.localdate(),
            first_name='Test',
            last_name='Client',
            phone1=998901112233,
            status=Order.Status.ORDERED,
            track_number='',
        )
        OrderItem.objects.create(
            order=order,
            product_name='Sneakers',
            product_quantity=1,
            product_price_currency='USD',
            product_price='120.000',
            store='Taobao',
        )

    def test_profile_page_renders(self):
        response = self.client.get(reverse('profile', args=[self.staff.username]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '@profileadmin')

    def test_profile_shorthand_redirects_to_current_user(self):
        response = self.client.get(f"{reverse('my_profile')}?sort=date_asc&status=ordered")
        expected = f"{reverse('profile', args=[self.staff.username])}?sort=date_asc&status=ordered"
        self.assertRedirects(response, expected, fetch_redirect_response=False)

    def test_profile_with_at_prefix_is_supported(self):
        response = self.client.get(reverse('profile', args=[f'@{self.staff.username}']))
        self.assertEqual(response.status_code, 200)

    def test_profile_filters_do_not_crash(self):
        query_strings = [
            '?status=ordered',
            '?sort=date_asc',
            '?sort=receipt_desc',
            '?sort=receipt_asc',
            '?sort=status_asc',
            '?sort=status_desc',
            '?date_from=2026-01-01&date_to=2026-12-31',
            '?search=Sneakers',
            '?status=invalid',
            '?date_from=invalid',
        ]

        for query in query_strings:
            with self.subTest(query=query):
                response = self.client.get(f"{reverse('profile', args=[self.staff.username])}{query}")
                self.assertEqual(response.status_code, 200)


class ErrorPageTests(TestCase):
    def test_404_page_is_rendered(self):
        response = self.client.get('/this-route-does-not-exist/')
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, '404', status_code=404)
        self.assertContains(response, 'Страница не найдена', status_code=404)


class StaffEntryPointTests(TestCase):
    def test_staff_login_is_available_without_trailing_slash(self):
        response = self.client.get(f"/{settings.STAFF_LOGIN_URL.rstrip('/')}")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Служебный вход')

    def test_panel_redirects_guest_to_staff_login(self):
        response = self.client.get(reverse('panel'))
        self.assertRedirects(
            response,
            reverse('staff_login'),
            fetch_redirect_response=False,
        )

    def test_panel_without_slash_redirects_guest_to_staff_login(self):
        response = self.client.get('/panel')
        self.assertRedirects(
            response,
            reverse('staff_login'),
            fetch_redirect_response=False,
        )

    def test_panel_redirects_staff_to_orders(self):
        password = get_random_string(24)
        user = User.objects.create_user(
            username='panelstaff',
            password=password,
            is_staff=True,
            is_active=True,
        )
        self.client.login(username=user.username, password=password)
        response = self.client.get(reverse('panel'))
        self.assertRedirects(response, reverse('orders'), fetch_redirect_response=False)

    def test_panel_redirects_superuser_to_admin(self):
        password = get_random_string(24)
        superuser = User.objects.create_superuser(
            username='panelroot',
            password=password,
            email='panelroot@example.com',
        )
        self.client.login(username=superuser.username, password=password)
        response = self.client.get(reverse('panel'))
        self.assertRedirects(
            response,
            f'/{settings.ADMIN_URL}',
            fetch_redirect_response=False,
        )

    def test_admin_is_available_without_trailing_slash(self):
        response = self.client.get(f'/{settings.ADMIN_URL.rstrip("/")}')
        self.assertRedirects(
            response,
            f'/{settings.ADMIN_URL}',
            fetch_redirect_response=False,
        )


class DispatchOrdersTests(TestCase):
    def setUp(self):
        password = get_random_string(24)
        self.staff = User.objects.create_user(
            username='dispatchstaff',
            password=password,
            is_staff=True,
            is_active=True,
        )
        self.client.login(username=self.staff.username, password=password)
        self.order = Order.objects.create(
            user=self.staff,
            receipt_number=431,
            order_date=timezone.localdate(),
            first_name='Daily',
            last_name='Client',
            phone1=998901234567,
            status=Order.Status.ACCEPTED,
            shipping_method=Order.ShippingMethod.AVIA,
        )
        Order.objects.create(
            user=self.staff,
            receipt_number=999,
            order_date=timezone.localdate(),
            first_name='Other',
            last_name='Name',
            phone1=998909999999,
            status=Order.Status.ORDERED,
            shipping_method=Order.ShippingMethod.IPOST,
        )

    def test_dispatch_page_renders(self):
        response = self.client.get(reverse('dispatch_orders'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Заказы на отправку')
        self.assertContains(response, '№431')

    def test_dispatch_page_shows_only_new_orders(self):
        response = self.client.get(reverse('dispatch_orders'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '№431')
        self.assertNotContains(response, '№999')

    def test_dispatch_page_can_update_order_status(self):
        response = self.client.post(
            reverse('dispatch_orders'),
            {
                'order_id': self.order.id,
                'status': Order.Status.TRANSIT,
            },
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.TRANSIT)

    def test_dispatch_page_has_no_filter_or_search_ui(self):
        response = self.client.get(reverse('dispatch_orders'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Поиск (квитанция / имя)')
        self.assertNotContains(response, 'За день')

    def test_dispatch_order_disappears_after_marked_ordered(self):
        response = self.client.post(
            reverse('dispatch_orders'),
            {
                'order_id': self.order.id,
                'status': Order.Status.ORDERED,
            },
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        response_after = self.client.get(reverse('dispatch_orders'))
        self.assertNotContains(response_after, 'Daily Client')
        self.assertContains(response_after, 'Новых заказов нет')


class TrackReminderDismissTests(TestCase):
    def setUp(self):
        password = get_random_string(24)
        self.staff = User.objects.create_user(
            username='noticeadmin',
            password=password,
            is_staff=True,
            is_active=True,
        )
        self.client.login(username=self.staff.username, password=password)
        Order.objects.create(
            user=self.staff,
            receipt_number=741,
            order_date=timezone.localdate() - timedelta(days=3),
            first_name='Track',
            last_name='Missing',
            phone1=998901010101,
            status=Order.Status.ORDERED,
            track_number='',
        )

    def test_track_notice_can_be_dismissed_and_reappears_later(self):
        home_url = reverse('index')
        response = self.client.get(home_url)
        self.assertContains(response, 'без трек-номера')

        dismiss_response = self.client.post(
            reverse('dismiss_track_notice'),
            {'next': home_url},
            follow=False,
        )
        self.assertEqual(dismiss_response.status_code, 302)

        response_after_dismiss = self.client.get(home_url)
        self.assertNotContains(response_after_dismiss, 'без трек-номера')

        session = self.client.session
        session[TRACK_NOTICE_DISMISS_KEY] = (timezone.now() - timedelta(days=3)).isoformat()
        session.save()

        response_after_expire = self.client.get(home_url)
        self.assertContains(response_after_expire, 'без трек-номера')


class NumberFormatFilterTests(TestCase):
    def test_money_adds_space_grouping_for_large_values(self):
        self.assertEqual(money('1000000'), '1 000 000')
        self.assertEqual(money('500000'), '500 000')

    def test_money_keeps_fraction_only_when_needed(self):
        self.assertEqual(money('1234567.50'), '1 234 567.5')
        self.assertEqual(money('1234567.567', 3), '1 234 567.567')


class CreateOrderFlowTests(TestCase):
    def setUp(self):
        password = get_random_string(24)
        self.staff = User.objects.create_user(
            username='createorderstaff',
            password=password,
            is_staff=True,
            is_active=True,
        )
        self.client.login(username=self.staff.username, password=password)

    def test_create_order_template_defaults_new_item_currency_to_uzs(self):
        response = self.client.get(reverse('create_order'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<option value="UZS" selected>UZS</option>', html=False)

    def test_create_order_disables_costs_when_toggles_unchecked(self):
        response = self.client.post(
            reverse('create_order'),
            {
                'receipt_number': '1001',
                'order_date': timezone.localdate().strftime('%Y-%m-%d'),
                'first_name': 'Ali',
                'last_name': 'Karimov',
                'phone1': '+998901112233',
                'phone2': '',
                'debt': '0',
                'shipping_method': Order.ShippingMethod.AVIA,
                'status': Order.Status.ACCEPTED,
                'track_pending': 'on',
                'track_number': '',
                # toggles intentionally unchecked
                'cargo_cost': '50000',
                'service_cost': '25000',
                'usd_rate': '12205',
                'rmb_rate': '1807',
                'description': '',
                'items-TOTAL_FORMS': '1',
                'items-INITIAL_FORMS': '0',
                'items-MIN_NUM_FORMS': '0',
                'items-MAX_NUM_FORMS': '1000',
                'items-0-product_name': 'Sneakers',
                'items-0-product_quantity': '1',
                'items-0-product_price_currency': 'UZS',
                'items-0-product_price': '100000',
                'items-0-store': 'Taobao',
                'items-0-link': '',
                'items-0-DELETE': '',
            },
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        order = Order.objects.get(receipt_number=1001)
        self.assertFalse(order.cargo_enabled)
        self.assertFalse(order.service_enabled)
        self.assertEqual(str(order.cargo_cost), '0.00')
        self.assertEqual(str(order.service_cost), '0.00')

    def test_create_order_supports_mixed_currencies_and_converts_to_uzs_total(self):
        response = self.client.post(
            reverse('create_order'),
            {
                'receipt_number': '1002',
                'order_date': timezone.localdate().strftime('%Y-%m-%d'),
                'first_name': 'Val',
                'last_name': 'Mix',
                'phone1': '+998909998877',
                'phone2': '',
                'debt': '0',
                'shipping_method': Order.ShippingMethod.AVIA,
                'status': Order.Status.ACCEPTED,
                'track_pending': 'on',
                'track_number': '',
                'cargo_enabled': 'on',
                'cargo_cost': '0',
                'service_enabled': 'on',
                'service_cost': '0',
                'usd_rate': '12205',
                'rmb_rate': '1807',
                'description': '',
                'items-TOTAL_FORMS': '2',
                'items-INITIAL_FORMS': '0',
                'items-MIN_NUM_FORMS': '0',
                'items-MAX_NUM_FORMS': '1000',
                'items-0-product_name': 'USD item',
                'items-0-product_quantity': '10',
                'items-0-product_price_currency': 'USD',
                'items-0-product_price': '1',
                'items-0-store': 'Taobao',
                'items-0-link': '',
                'items-0-DELETE': '',
                'items-1-product_name': 'RMB item',
                'items-1-product_quantity': '100',
                'items-1-product_price_currency': 'RMB',
                'items-1-product_price': '1',
                'items-1-store': 'Alibaba',
                'items-1-link': '',
                'items-1-DELETE': '',
            },
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        order = Order.objects.get(receipt_number=1002)
        self.assertEqual(order.items.count(), 2)
        self.assertEqual(order.get_current, 'UZS')
        self.assertEqual(order.get_total_price, Decimal('302750.00'))


class ExcelImportExportTests(TestCase):
    def setUp(self):
        password = get_random_string(24)
        self.staff = User.objects.create_user(
            username='excelstaff',
            password=password,
            is_staff=True,
            is_active=True,
        )
        self.client.login(username=self.staff.username, password=password)

        self.order = Order.objects.create(
            user=self.staff,
            receipt_number=2001,
            order_date=timezone.localdate(),
            first_name='Excel',
            last_name='User',
            phone1=998901111111,
            shipping_method=Order.ShippingMethod.AVIA,
            status=Order.Status.ACCEPTED,
        )
        OrderItem.objects.create(
            order=self.order,
            product_name='Sneakers',
            product_quantity=2,
            product_price_currency='UZS',
            product_price='150000.000',
            store='Taobao',
        )

    def test_orders_export_excel_returns_xlsx(self):
        response = self.client.get(reverse('orders_export_excel'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('spreadsheetml', response['Content-Type'])

        workbook = load_workbook(BytesIO(response.content), data_only=True)
        sheet = workbook.active
        self.assertEqual(sheet.cell(1, 2).value, 'Квитанция')
        self.assertEqual(sheet.cell(2, 2).value, 2001)

    def test_orders_import_excel_creates_order_and_items(self):
        workbook = Workbook()
        sheet = workbook.active
        sheet.append([
            'Slug', 'Квитанция', 'Дата заказа', 'Имя клиента', 'Фамилия клиента',
            'Телефон #1', 'Телефон #2', 'Тип отправки', 'Статус', 'Трек-номер',
            'Трек ожидается', 'Карго включено', 'Карго сумма', 'Услуга включена',
            'Услуга сумма', 'Долг', 'Комментарий', 'Название товара', 'Количество',
            'Валюта', 'Себестоимость', 'Магазин', 'Ссылка', 'Админ',
        ])
        sheet.append([
            '', 3001, timezone.localdate().strftime('%Y-%m-%d'), 'Ali', 'Karimov',
            '+998901223344', '', 'AVIA', 'accepted', '', 'Да', 'Да', '0', 'Да',
            '0', '', '', 'Кроссовки', 1, 'UZS', '250000', 'Taobao', '', self.staff.username,
        ])

        payload = BytesIO()
        workbook.save(payload)
        payload.seek(0)
        uploaded = SimpleUploadedFile(
            'orders_import.xlsx',
            payload.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

        response = self.client.post(
            reverse('orders_import_excel'),
            {'excel_file': uploaded, 'next': reverse('orders')},
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        imported = Order.objects.get(receipt_number=3001)
        self.assertEqual(imported.first_name, 'Ali')
        self.assertEqual(imported.items.count(), 1)


class FullSiteRegressionLoadTests(TestCase):
    """Pre-production smoke/load tests for core views with 100 orders."""

    @classmethod
    def setUpTestData(cls):
        cls.staff_password = get_random_string(24)
        cls.staff = User.objects.create_user(
            username='loadstaff',
            password=cls.staff_password,
            is_staff=True,
            is_active=True,
        )

        cls.other_staff_password = get_random_string(24)
        cls.other_staff = User.objects.create_user(
            username='loadstaff2',
            password=cls.other_staff_password,
            is_staff=True,
            is_active=True,
        )

        cls.super_password = get_random_string(24)
        cls.superuser = User.objects.create_superuser(
            username='loadroot',
            password=cls.super_password,
            email='loadroot@example.com',
        )

        cls.client_password = get_random_string(24)
        cls.client_user = User.objects.create_user(
            username='regularclient',
            password=cls.client_password,
            is_staff=False,
            is_active=True,
        )

        today = timezone.localdate()
        status_cycle = [
            Order.Status.ACCEPTED,
            Order.Status.ORDERED,
            Order.Status.TRANSIT,
            Order.Status.ARRIVED,
            Order.Status.CANCELLED,
        ]
        shipping_cycle = [
            Order.ShippingMethod.AVIA,
            Order.ShippingMethod.IPOST,
            Order.ShippingMethod.CARGO_17994,
        ]
        store_cycle = ['Taobao', 'Alibaba', 'AliExpress', 'Pinduoduo', 'Poizon', '1688', '95', 'MadeChina']

        for idx in range(1, 101):
            owner = cls.staff if idx % 2 else cls.other_staff
            status = status_cycle[idx % len(status_cycle)]
            order = Order.objects.create(
                user=owner,
                receipt_number=400 + idx,
                order_date=today - timedelta(days=idx % 35),
                first_name=f'Client{idx}',
                last_name='Load',
                phone1=998900000000 + idx,
                status=status,
                shipping_method=shipping_cycle[idx % len(shipping_cycle)],
                track_number='' if idx % 3 == 0 else f'TRK{idx:06d}',
                cargo_enabled=(idx % 4 != 0),
                cargo_cost=Decimal('17000.00') if idx % 4 != 0 else Decimal('0.00'),
                service_enabled=(idx % 5 != 0),
                service_cost=Decimal('9000.00') if idx % 5 != 0 else Decimal('0.00'),
                description=f'Load dataset order #{idx}',
            )
            OrderItem.objects.create(
                order=order,
                product_name=f'Product {idx}',
                product_quantity=(idx % 4) + 1,
                product_price_currency='UZS',
                product_price=Decimal('125000.000') + Decimal(idx),
                store=store_cycle[idx % len(store_cycle)],
                link=f'https://example.com/order/{idx}',
            )
            if idx % 2 == 0:
                OrderAttachment.objects.create(
                    order=order,
                    image=f'orders/images/load_{idx}.jpg',
                )

        cls.sample_order = Order.objects.filter(user=cls.staff).order_by('id').first()

    def _login_staff(self):
        self.client.logout()
        self.assertTrue(self.client.login(username=self.staff.username, password=self.staff_password))

    def _login_superuser(self):
        self.client.logout()
        self.assertTrue(self.client.login(username=self.superuser.username, password=self.super_password))

    def _login_client(self):
        self.client.logout()
        self.assertTrue(self.client.login(username=self.client_user.username, password=self.client_password))

    def test_public_views_and_hidden_routes(self):
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('staff_login'))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('about'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'AkmalExpress')

        response = self.client.get(reverse('contacts'))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('robots_txt'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Disallow: /order/')

        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 404)

        response = self.client.get('/admin/')
        self.assertEqual(response.status_code, 404)

        detail_response = self.client.get(reverse('detail_order', args=[self.sample_order.slug]))
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, f'№{self.sample_order.receipt_number}')
        self.assertNotContains(detail_response, 'Печать квитанции')

        lang_url = reverse('set_language', args=['uz'])
        response = self.client.get(f'{lang_url}?next={reverse("about")}', follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('about'))
        self.assertIsNotNone(response.cookies.get('site_language'))

    def test_access_control_for_regular_user(self):
        self._login_client()
        restricted_get_urls = [
            reverse('orders'),
            reverse('create_order'),
            reverse('dispatch_orders'),
            reverse('print_receipt', args=[self.sample_order.slug]),
            reverse('profile', args=[self.staff.username]),
            reverse('orders_export_excel'),
            reverse('create_admin'),
        ]

        for url in restricted_get_urls:
            with self.subTest(url=url):
                response = self.client.get(url, follow=False)
                self.assertEqual(response.status_code, 302)

        response = self.client.get(reverse('detail_order', args=[self.sample_order.slug]))
        self.assertEqual(response.status_code, 200)

    def test_staff_views_under_load(self):
        self._login_staff()
        today = timezone.localdate().strftime('%Y-%m-%d')

        for page in range(1, 7):
            response = self.client.get(reverse('orders'), {'page': page})
            self.assertEqual(response.status_code, 200)

        for _ in range(3):
            response = self.client.get(reverse('dispatch_orders'), {'page': 1})
            self.assertEqual(response.status_code, 200)

        profile_url = reverse('profile', args=[self.staff.username])
        profile_queries = [
            {'search': 'Client', 'status': Order.Status.ACCEPTED, 'sort': 'date_desc', 'page': 1},
            {'search': 'Product', 'status': '', 'sort': 'receipt_asc', 'page': 2},
            {'date_from': (timezone.localdate() - timedelta(days=30)).strftime('%Y-%m-%d'), 'date_to': today},
        ]
        for query in profile_queries:
            response = self.client.get(profile_url, query)
            self.assertEqual(response.status_code, 200)

        for order in Order.objects.order_by('-id')[:15]:
            response = self.client.get(reverse('detail_order', args=[order.slug]))
            self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('print_receipt', args=[self.sample_order.slug]))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('create_product'))
        self.assertRedirects(response, reverse('create_order'), fetch_redirect_response=False)

        response = self.client.get(reverse('panel'))
        self.assertRedirects(response, reverse('orders'), fetch_redirect_response=False)

        response = self.client.post(reverse('dismiss_track_notice'), {'next': reverse('orders')}, follow=False)
        self.assertEqual(response.status_code, 302)

        response = self.client.get(reverse('my_profile'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('profile', args=[self.staff.username]), response.url)

        response = self.client.get(reverse('logout'))
        self.assertEqual(response.status_code, 302)

    def test_repeated_requests_stability(self):
        """Run repeated requests against core pages over a 100-order dataset."""
        self._login_staff()
        today = timezone.localdate().strftime('%Y-%m-%d')
        sample_slugs = list(Order.objects.order_by('-id').values_list('slug', flat=True)[:20])
        base_urls = [
            f"{reverse('index')}?search=Client",
            f"{reverse('orders')}?page=1",
            f"{reverse('dispatch_orders')}?page=1",
            f"{reverse('profile', args=[self.staff.username])}?search=Client&page=1",
        ]

        for _ in range(5):
            for url in base_urls:
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
            for slug in sample_slugs:
                response = self.client.get(reverse('detail_order', args=[slug]))
                self.assertEqual(response.status_code, 200)

    def test_superuser_admin_and_management_views(self):
        self._login_superuser()
        response = self.client.get(reverse('create_admin'))
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            reverse('create_admin'),
            {'username': 'newmoderator', 'password1': 'P@ssword-12345', 'password2': 'P@ssword-12345'},
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        new_admin = User.objects.get(username='newmoderator')
        self.assertTrue(new_admin.is_staff)
        self.assertTrue(new_admin.is_active)

        response = self.client.post(
            reverse('toggle_status', args=[new_admin.id]),
            {'action': 'deactivate'},
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        new_admin.refresh_from_db()
        self.assertFalse(new_admin.is_staff)
        self.assertFalse(new_admin.is_active)

        response = self.client.post(
            reverse('toggle_status', args=[new_admin.id]),
            {'action': 'activate'},
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        new_admin.refresh_from_db()
        self.assertTrue(new_admin.is_staff)
        self.assertTrue(new_admin.is_active)

        response = self.client.post(reverse('delete_admin', args=[new_admin.id]), follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.filter(username='newmoderator').exists())

        # Guard rails for superusers should remain active.
        response = self.client.post(reverse('delete_admin', args=[self.superuser.id]), follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username=self.superuser.username).exists())

        response = self.client.get(reverse('toggle_status', args=[self.staff.id]), follow=False)
        self.assertEqual(response.status_code, 405)

    def test_create_change_delete_order_flow(self):
        self._login_staff()

        create_payload = {
            'receipt_number': '1499',
            'order_date': timezone.localdate().strftime('%Y-%m-%d'),
            'first_name': 'Flow',
            'last_name': 'Case',
            'phone1': '+998901010303',
            'phone2': '',
            'debt': '0',
            'shipping_method': Order.ShippingMethod.AVIA,
            'status': Order.Status.ACCEPTED,
            'track_pending': 'on',
            'track_number': '',
            'cargo_enabled': 'on',
            'cargo_cost': '17000',
            'service_enabled': 'on',
            'service_cost': '9000',
            'usd_rate': '12205',
            'rmb_rate': '1807',
            'description': 'Regression CRUD flow',
            'items-TOTAL_FORMS': '2',
            'items-INITIAL_FORMS': '0',
            'items-MIN_NUM_FORMS': '0',
            'items-MAX_NUM_FORMS': '1000',
            'items-0-product_name': 'Jacket',
            'items-0-product_quantity': '1',
            'items-0-product_price_currency': 'UZS',
            'items-0-product_price': '320000',
            'items-0-store': 'Taobao',
            'items-0-link': 'https://example.com/jacket',
            'items-0-DELETE': '',
            'items-1-product_name': 'Shoes',
            'items-1-product_quantity': '2',
            'items-1-product_price_currency': 'UZS',
            'items-1-product_price': '210000',
            'items-1-store': '95',
            'items-1-link': 'https://example.com/shoes',
            'items-1-DELETE': '',
        }
        response = self.client.post(reverse('create_order'), create_payload, follow=False)
        self.assertEqual(response.status_code, 302)

        created_order = Order.objects.get(receipt_number=1499)
        self.assertEqual(created_order.items.count(), 2)
        self.assertEqual(created_order.items.filter(link__isnull=False).count(), 2)

        change_payload = {
            'receipt_number': str(created_order.receipt_number),
            'order_date': created_order.order_date.strftime('%Y-%m-%d'),
            'shipping_method': created_order.shipping_method,
            'track_number': 'TRACK-FLOW-001',
            'first_name': created_order.first_name,
            'last_name': created_order.last_name,
            'phone1': str(created_order.phone1),
            'phone2': '',
            'debt': '0',
            'cargo_enabled': 'on',
            'cargo_cost': '19000',
            'service_enabled': 'on',
            'service_cost': '10000',
            'usd_rate': '12205',
            'rmb_rate': '1807',
            'description': 'Updated flow',
            'status': Order.Status.TRANSIT,
        }
        response = self.client.post(
            reverse('change_order', args=[created_order.slug]),
            change_payload,
            follow=False,
        )
        self.assertEqual(response.status_code, 302)

        created_order.refresh_from_db()
        self.assertEqual(created_order.status, Order.Status.TRANSIT)
        self.assertEqual(created_order.track_number, 'TRACK-FLOW-001')

        response = self.client.get(reverse('delete_order', args=[created_order.slug]))
        self.assertEqual(response.status_code, 200)
        response = self.client.post(reverse('delete_order', args=[created_order.slug]), follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Order.objects.filter(receipt_number=1499).exists())

    def test_excel_import_export_for_orders_and_profiles(self):
        self._login_staff()

        response = self.client.get(reverse('orders_export_excel'))
        self.assertEqual(response.status_code, 200)
        workbook = load_workbook(BytesIO(response.content), data_only=True)
        self.assertGreaterEqual(workbook.active.max_row, 101)

        response = self.client.get(reverse('profile_export_excel', args=[self.staff.username]))
        self.assertEqual(response.status_code, 200)
        profile_workbook = load_workbook(BytesIO(response.content), data_only=True)
        self.assertGreaterEqual(profile_workbook.active.max_row, 2)

        workbook_to_import = Workbook()
        sheet = workbook_to_import.active
        sheet.append([
            'Slug', 'Квитанция', 'Дата заказа', 'Имя клиента', 'Фамилия клиента',
            'Телефон #1', 'Телефон #2', 'Тип отправки', 'Статус', 'Трек-номер',
            'Трек ожидается', 'Карго включено', 'Карго сумма', 'Услуга включена',
            'Услуга сумма', 'Долг', 'Комментарий', 'Название товара', 'Количество',
            'Валюта', 'Себестоимость', 'Магазин', 'Ссылка', 'Админ',
        ])
        sheet.append([
            '', 1498, timezone.localdate().strftime('%Y-%m-%d'), 'Excel', 'Load',
            '+998901000001', '', 'AVIA', 'accepted', '', 'Да', 'Да', '15000', 'Да',
            '8000', '', 'bulk import 1', 'Bag', 1, 'UZS', '145000', 'Taobao',
            'https://example.com/bag', self.staff.username,
        ])
        sheet.append([
            '', 1498, timezone.localdate().strftime('%Y-%m-%d'), 'Excel', 'Load',
            '+998901000001', '', 'AVIA', 'accepted', '', 'Да', 'Да', '15000', 'Да',
            '8000', '', 'bulk import 1', 'Hat', 2, 'UZS', '85000', 'Alibaba',
            'https://example.com/hat', self.staff.username,
        ])

        payload = BytesIO()
        workbook_to_import.save(payload)
        payload.seek(0)
        uploaded = SimpleUploadedFile(
            'bulk_orders.xlsx',
            payload.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

        response = self.client.post(
            reverse('orders_import_excel'),
            {'excel_file': uploaded, 'next': reverse('orders')},
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        imported = Order.objects.get(receipt_number=1498, first_name='Excel', phone1=998901000001)
        self.assertEqual(imported.items.count(), 2)

        profile_wb = Workbook()
        profile_sheet = profile_wb.active
        profile_sheet.append([
            'Slug', 'Квитанция', 'Дата заказа', 'Имя клиента', 'Фамилия клиента',
            'Телефон #1', 'Телефон #2', 'Тип отправки', 'Статус', 'Трек-номер',
            'Трек ожидается', 'Карго включено', 'Карго сумма', 'Услуга включена',
            'Услуга сумма', 'Долг', 'Комментарий', 'Название товара', 'Количество',
            'Валюта', 'Себестоимость', 'Магазин', 'Ссылка', 'Админ',
        ])
        profile_sheet.append([
            '', 1497, timezone.localdate().strftime('%Y-%m-%d'), 'Profile', 'Import',
            '+998901000002', '', 'iPost', 'ordered', '', 'Да', 'Да', '10000', 'Да',
            '5000', '', '', 'Backpack', 1, 'UZS', '120000', '95', 'https://example.com/backpack', '',
        ])
        profile_payload = BytesIO()
        profile_wb.save(profile_payload)
        profile_payload.seek(0)
        profile_uploaded = SimpleUploadedFile(
            'profile_orders.xlsx',
            profile_payload.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

        response = self.client.post(
            reverse('profile_import_excel', args=[self.other_staff.username]),
            {'excel_file': profile_uploaded, 'next': reverse('profile', args=[self.other_staff.username])},
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        profile_imported = Order.objects.get(receipt_number=1497, first_name='Profile')
        self.assertEqual(profile_imported.user, self.other_staff)
