from django.core.management.base import BaseCommand

from referrals.services.codes import backfill_missing_referral_profiles


class Command(BaseCommand):
    help = 'Create ReferralProfile rows for customers missing a referral code.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=None)

    def handle(self, *args, **options):
        created = backfill_missing_referral_profiles(limit=options['limit'])
        self.stdout.write(self.style.SUCCESS(f'Created {created} referral profile(s).'))
