"""
Seed adatok — alapértelmezett beállítások létrehozása.
Idempotens: get_or_create-t használ, nem írja felül a meglévő adatokat.
"""

from django.core.management.base import BaseCommand
from naptar.models import Settings


class Command(BaseCommand):
    help = 'Alapértelmezett beállítások és seed adatok létrehozása'

    def handle(self, *args, **options):
        # Beállítások létrehozása (ha még nincs)
        settings, created = Settings.objects.get_or_create(pk=1)

        if created:
            self.stdout.write(self.style.SUCCESS('✅ Alapértelmezett beállítások létrehozva.'))
        else:
            self.stdout.write(self.style.WARNING('ℹ️  A beállítások már léteznek, kihagyva.'))

        self.stdout.write(f'   Munkaidő: {settings.workday_start} – {settings.workday_end}')
        self.stdout.write(f'   Ebédszünet: {settings.lunch_break_start} – {settings.lunch_break_end}')
        self.stdout.write(f'   Napi óra: {settings.default_daily_hours} (max {settings.max_daily_hours})')
