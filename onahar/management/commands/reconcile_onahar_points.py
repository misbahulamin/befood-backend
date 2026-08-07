from django.core.management.base import BaseCommand

from onahar.models import OnaharPointEvent
from onahar.services.contribution import credit_for_delivery, is_onahar_enabled


class Command(BaseCommand):
    help = (
        'Reconcile delivered OrderDelivery rows that are missing an Onahar credit '
        'point event. Safe to re-run (idempotent credits).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report missing credits without writing',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=500,
            help='Max deliveries to process',
        )

    def handle(self, *args, **options):
        if not is_onahar_enabled():
            self.stdout.write(self.style.WARNING('ONAHAR_ENABLED is false; aborting.'))
            return

        from orders.models import OrderDelivery

        credited_ids = OnaharPointEvent.objects.filter(
            event_type=OnaharPointEvent.EventType.CREDIT,
        ).values_list('order_delivery_id', flat=True)

        qs = (
            OrderDelivery.objects.filter(status=OrderDelivery.DeliveryStatus.DELIVERED)
            .exclude(pk__in=credited_ids)
            .select_related('order__customer')
            .order_by('id')[: options['limit']]
        )
        missing = list(qs)
        self.stdout.write(f'Missing Onahar credits: {len(missing)}')
        if options['dry_run']:
            return

        created = 0
        for delivery in missing:
            event = credit_for_delivery(delivery)
            if event is not None:
                created += 1
        self.stdout.write(self.style.SUCCESS(f'Credited {created} deliveries.'))
