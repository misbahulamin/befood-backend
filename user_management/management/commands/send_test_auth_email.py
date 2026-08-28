from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from user_management.models import CustomerProfile
from user_management.services.email_verification import send_activation_email
from user_management.services.password_reset import send_password_reset_email


DEFAULT_TO = 'misbahul.amin.ai@gmail.com'


class Command(BaseCommand):
    help = (
        'Send a sample branded auth email (activation or password_reset) '
        'for visual QA via configured SMTP.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            choices=('activation', 'password_reset'),
            default='activation',
            help='Which branded email to send.',
        )
        parser.add_argument(
            '--to',
            default=DEFAULT_TO,
            help=f'Destination address (default: {DEFAULT_TO}).',
        )
        parser.add_argument(
            '--first-name',
            default='Misbahul',
            help='Sample first name used in the greeting.',
        )
        parser.add_argument(
            '--gender',
            choices=('male', 'female', ''),
            default='male',
            help='Sample gender for bhaiya/apu greeting (empty = unknown).',
        )

    def handle(self, *args, **options):
        email_type = options['type']
        to_email = options['to'].strip().lower()
        if not to_email:
            raise CommandError('--to must be a non-empty email address.')

        user, _ = User.objects.get_or_create(
            username=to_email,
            defaults={
                'email': to_email,
                'first_name': options['first_name'],
                'is_active': False,
            },
        )
        changed = False
        if user.email != to_email:
            user.email = to_email
            changed = True
        if options['first_name'] and user.first_name != options['first_name']:
            user.first_name = options['first_name']
            changed = True
        if changed:
            user.save()

        profile, _ = CustomerProfile.objects.get_or_create(user=user)
        gender = options['gender'] or None
        if profile.gender != gender:
            profile.gender = gender
            profile.save(update_fields=['gender', 'updated_at'])

        if email_type == 'activation':
            # Request is only used for absolute activation URL building.
            from django.test import RequestFactory

            request = RequestFactory().get('/')
            request.META['HTTP_HOST'] = 'api.befood.com.bd'
            request.META['wsgi.url_scheme'] = 'https'
            send_activation_email(request, user)
            self.stdout.write(self.style.SUCCESS(f'Sent activation email to {to_email}'))
            return

        send_password_reset_email(user)
        self.stdout.write(self.style.SUCCESS(f'Sent password-reset email to {to_email}'))
