import base64
from decimal import Decimal
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone

from akmalexpress.models import Order, OrderAttachment, OrderItem, Product


TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII="
)


class Command(BaseCommand):
    help = "Create demo orders with items, links and optional photos for local testing."

    def add_arguments(self, parser):
        parser.add_argument('--count', type=int, default=100, help='How many orders to create (default: 100)')
        parser.add_argument('--clear', action='store_true', help='Delete all existing orders before seeding')
        parser.add_argument(
            '--without-photos',
            action='store_true',
            help='Do not create photo attachments',
        )
        parser.add_argument('--admin-username', default='admin', help='Fallback superuser username')
        parser.add_argument('--admin-password', default='admin12345', help='Fallback superuser password')
        parser.add_argument('--staff-username', default='manager', help='Fallback staff username')
        parser.add_argument('--staff-password', default='manager12345', help='Fallback staff password')

    def _ensure_admin_users(self, options):
        users = list(User.objects.filter(is_active=True).filter(Q(is_staff=True) | Q(is_superuser=True)).order_by('id'))
        created_messages = []

        if users:
            return users, created_messages

        superuser = User.objects.filter(username=options['admin_username']).first()
        if superuser is None:
            superuser = User.objects.create_superuser(
                username=options['admin_username'],
                email='admin@example.com',
                password=options['admin_password'],
            )
            created_messages.append(
                f"Created superuser: {superuser.username} / {options['admin_password']}"
            )
        elif not superuser.is_superuser:
            superuser.is_superuser = True
            superuser.is_staff = True
            superuser.is_active = True
            superuser.set_password(options['admin_password'])
            superuser.save(update_fields=['is_superuser', 'is_staff', 'is_active', 'password'])
            created_messages.append(
                f"Updated user to superuser: {superuser.username} / {options['admin_password']}"
            )

        staff_user = User.objects.filter(username=options['staff_username']).first()
        if staff_user is None:
            staff_user = User.objects.create_user(
                username=options['staff_username'],
                password=options['staff_password'],
                is_staff=True,
                is_active=True,
            )
            created_messages.append(
                f"Created staff user: {staff_user.username} / {options['staff_password']}"
            )
        elif not (staff_user.is_staff and staff_user.is_active):
            staff_user.is_staff = True
            staff_user.is_active = True
            staff_user.set_password(options['staff_password'])
            staff_user.save(update_fields=['is_staff', 'is_active', 'password'])
            created_messages.append(
                f"Updated user to staff: {staff_user.username} / {options['staff_password']}"
            )

        users = list(User.objects.filter(is_active=True).filter(Q(is_staff=True) | Q(is_superuser=True)).order_by('id'))
        return users, created_messages

    def _build_image_file(self, receipt_number, sequence):
        image_bytes = base64.b64decode(TINY_PNG_B64)
        return ContentFile(image_bytes, name=f'order_{receipt_number}_{sequence}.png')

    def handle(self, *args, **options):
        count = options['count']
        if count < 1:
            raise CommandError('--count must be greater than 0')
        if count > 1500:
            raise CommandError('--count cannot be greater than 1500 (receipt_number model limit)')

        with_photos = not options['without_photos']
        today = timezone.localdate()

        if options['clear']:
            Order.objects.all().delete()
            self.stdout.write(self.style.WARNING('All existing orders were deleted.'))

        users, created_messages = self._ensure_admin_users(options)
        if not users:
            raise CommandError('No active staff/superuser accounts available for order ownership.')

        for message in created_messages:
            self.stdout.write(self.style.WARNING(message))

        last_receipt = Order.objects.order_by('-receipt_number').values_list('receipt_number', flat=True).first()
        start_receipt = (last_receipt + 1) if last_receipt else 1
        end_receipt = start_receipt + count - 1
        if end_receipt > 1500:
            raise CommandError(
                f'Cannot create {count} orders from receipt #{start_receipt}. '
                f'Max allowed receipt is 1500. Use --clear or lower count.'
            )

        first_names = [
            'Akmal', 'Aziza', 'Dilshod', 'Malika', 'Sardor', 'Nigora', 'Bekzod',
            'Shahzoda', 'Jamshid', 'Umida', 'Suhrob', 'Madina',
        ]
        last_names = [
            'Karimov', 'Islomov', 'Rasulov', 'Tursunova', 'Mirzaev', 'Saidova',
            'Qodirov', 'Umarova', 'Nazarov', 'Alimuhamedov',
        ]
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
        store_cycle = [
            Product.Store.TAOBAO,
            Product.Store.ALIBABA,
            Product.Store.ALIEXPRESS,
            Product.Store.PINDUODUO,
            Product.Store.POIZON,
            Product.Store.SIX,
            Product.Store.NINETY_FIVE,
            Product.Store.MADE_IN_CHINA,
        ]

        created_orders = 0
        created_items = 0
        created_attachments = 0

        for idx in range(count):
            receipt = start_receipt + idx
            user = users[idx % len(users)]
            status = status_cycle[idx % len(status_cycle)]
            order_date = today - timedelta(days=(idx % 45))
            track_number = '' if (idx % 3 == 0) else f'TRK{receipt:06d}'

            order = Order.objects.create(
                user=user,
                receipt_number=receipt,
                order_date=order_date,
                shipping_method=shipping_cycle[idx % len(shipping_cycle)],
                status=status,
                track_number=track_number,
                first_name=first_names[idx % len(first_names)],
                last_name=last_names[idx % len(last_names)],
                phone1=998900000000 + receipt,
                phone2=998901000000 + receipt if idx % 4 == 0 else None,
                debt=Decimal('0.00') if idx % 5 else Decimal('20000.00'),
                cargo_enabled=(idx % 4 != 0),
                cargo_cost=Decimal('17000.00') if idx % 4 != 0 else Decimal('0.00'),
                service_enabled=(idx % 6 != 0),
                service_cost=Decimal('10000.00') if idx % 6 != 0 else Decimal('0.00'),
                description=f'Demo order #{receipt} created by seed command',
                come=timezone.now() if status == Order.Status.ARRIVED else None,
            )
            created_orders += 1

            items_count = 1 + (idx % 3)
            for item_idx in range(items_count):
                store = store_cycle[(idx + item_idx) % len(store_cycle)]
                currency = Product.Currency.UZS if item_idx % 2 == 0 else Product.Currency.USD
                price_value = Decimal('95000.000') + Decimal((idx + item_idx) * 3200)
                if currency == Product.Currency.USD:
                    price_value = Decimal('12.500') + Decimal((idx + item_idx) % 8)

                OrderItem.objects.create(
                    order=order,
                    product_name=f'Product {receipt}-{item_idx + 1}',
                    product_quantity=1 + ((idx + item_idx) % 4),
                    product_price_currency=currency,
                    product_price=price_value,
                    store=store,
                    link=f'https://example.com/product/{receipt}/{item_idx + 1}',
                )
                created_items += 1

            if with_photos and idx % 2 == 0:
                photos_count = 1 + (idx % 2)
                for photo_idx in range(photos_count):
                    image_file = self._build_image_file(receipt, photo_idx + 1)
                    OrderAttachment.objects.create(order=order, image=image_file)
                    created_attachments += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Seed completed: orders={created_orders}, items={created_items}, photos={created_attachments}.'
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'Receipt range: {start_receipt}..{end_receipt}. Active staff users used: {len(users)}.'
            )
        )

