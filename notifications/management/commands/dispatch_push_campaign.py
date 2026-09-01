from django.core.management.base import BaseCommand

from notifications.models import PushCampaign
from notifications.services.notification_sender import dispatch_push_campaign, get_stuck_campaign_ids


class Command(BaseCommand):
    help = 'Dispatch push campaigns (single campaign or stuck processing campaigns).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--campaign-id',
            dest='campaign_public_id',
            help='Public UUID of the campaign to dispatch.',
        )
        parser.add_argument(
            '--stuck-only',
            action='store_true',
            help='Process campaigns stuck in processing status.',
        )

    def handle(self, *args, **options):
        campaign_public_id = options.get('campaign_public_id')
        stuck_only = options.get('stuck_only')

        if campaign_public_id:
            try:
                campaign = PushCampaign.objects.get(public_id=campaign_public_id)
            except PushCampaign.DoesNotExist:
                self.stderr.write(self.style.ERROR(f'Campaign not found: {campaign_public_id}'))
                return
            dispatch_push_campaign(campaign.id)
            self.stdout.write(self.style.SUCCESS(f'Dispatched campaign {campaign_public_id}'))
            return

        if stuck_only:
            stuck_ids = get_stuck_campaign_ids()
            for campaign_id in stuck_ids:
                dispatch_push_campaign(campaign_id)
            self.stdout.write(self.style.SUCCESS(f'Dispatched {len(stuck_ids)} stuck campaign(s)'))
            return

        self.stderr.write(self.style.ERROR('Provide --campaign-id or --stuck-only'))
