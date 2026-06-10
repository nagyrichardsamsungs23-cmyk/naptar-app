"""
Seed adatok — alapértelmezett beállítások és admin felhasználó létrehozása.
Idempotens: get_or_create-t használ, nem írja felül a meglévő adatokat.
"""
import os
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from naptar.models import Settings


class Command(BaseCommand):
    help = 'Alapértelmezett beállítások, admin felhasználó és seed adatok létrehozása'

    def handle(self, *args, **options):
        # 1. Beállítások létrehozása (ha még nincs)
        settings, created = Settings.objects.get_or_create(pk=1)

        if created:
            self.stdout.write(self.style.SUCCESS('✅ Alapértelmezett beállítások létrehozva.'))
        else:
            self.stdout.write(self.style.WARNING('ℹ️  A beállítások már léteznek, kihagyva.'))

        sat_status = "aktív" if settings.sat_active else "szabadnap"
        sun_status = "aktív" if settings.sun_active else "szabadnap"
        self.stdout.write(f'   Hétfő–Péntek: {settings.mon_start}–{settings.mon_end}')
        self.stdout.write(f'   Szombat: {sat_status}')
        self.stdout.write(f'   Vasárnap: {sun_status}')
        self.stdout.write(f'   Max napi óra: {settings.max_daily_hours}')

        # 2. Admin felhasználó létrehozása (ha még nincs)
        admin_password = os.environ.get('ADMIN_PASSWORD', 'Admin1234')

        user, user_created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@naptar.hu',
                'is_staff': True,
                'is_superuser': True,
                'is_active': True,
            }
        )

        if user_created:
            user.set_password(admin_password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f'✅ Admin felhasználó létrehozva (admin / {admin_password}).'))
        else:
            updated = False
            if not user.is_staff or not user.is_superuser:
                user.is_staff = True
                user.is_superuser = True
                updated = True
            if not user.is_active:
                user.is_active = True
                updated = True
            if updated:
                user.save()
                self.stdout.write(self.style.SUCCESS('✅ Admin jogosultságok frissítve.'))
            else:
                self.stdout.write(self.style.WARNING('ℹ️  Admin felhasználó már létezik, kihagyva.'))
