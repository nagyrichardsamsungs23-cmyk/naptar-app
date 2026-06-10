"""
Management command: admin jelszó beállítása környezeti változóból.
A Railway-en az ADMIN_PASSWORD változóban tároljuk a jelszót.
"""
import os
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Beállítja az admin felhasználó jelszavát az ADMIN_PASSWORD környezeti változóból'

    def handle(self, *args, **options):
        password = os.environ.get('ADMIN_PASSWORD', '')
        if not password:
            self.stdout.write(self.style.WARNING(
                'ADMIN_PASSWORD változó nincs beállítva → jelszócsere kihagyva.'
            ))
            return

        try:
            user, created = User.objects.get_or_create(
                username='admin',
                defaults={
                    'email': 'admin@naptar.hu',
                    'is_staff': True,
                    'is_superuser': True,
                }
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f'HIBA: admin felhasználó létrehozása nem sikerült: {e}'
            ))
            return

        user.set_password(password)
        user.save()
        
        if created:
            self.stdout.write(self.style.SUCCESS(
                'Admin felhasználó létrehozva és jelszó beállítva.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                'Admin jelszó sikeresen beállítva.'
            ))
