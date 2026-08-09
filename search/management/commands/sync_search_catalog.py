from django.core.management.base import BaseCommand

from search.services.indexing import seed_common_keyword_packs, sync_search_catalog


class Command(BaseCommand):
    help = (
        'Upsert search documents from active meals/ingredients/category facets. '
        'Does not wipe curated keywords. Run after meal renames or catalog changes.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--seed-keywords',
            action='store_true',
            help='Also attach common Bangla/Banglish/English keyword packs.',
        )

    def handle(self, *args, **options):
        stats = sync_search_catalog()
        self.stdout.write(
            self.style.SUCCESS(
                f"Search catalog sync complete: created={stats['created']} updated={stats['updated']}"
            )
        )
        if options['seed_keywords']:
            added = seed_common_keyword_packs()
            self.stdout.write(self.style.SUCCESS(f'Seeded/ensured keywords (+{added} new rows).'))
