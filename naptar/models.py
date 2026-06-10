"""
Naptár Alkalmazás — Modellek
=============================
Építőipari munkaidő-tervező naptár.

Táblák:
  1. Job           — Munkák (projektek)
  2. WorkSchedule  — Naptárba tett munkaidő-beosztás
  3. TimeOff       — Tiltott időszakok (szabadság, ünnep, stb.)
  4. Settings      — Általános beállítások (egy rekord)
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal


class Job(models.Model):
    """Építőipari munka / projekt."""
    PRIORITY_CHOICES = [
        ('low', 'Alacsony'),
        ('medium', 'Normál'),
        ('high', 'Magas'),
        ('urgent', 'Sürgős'),
    ]
    STATUS_CHOICES = [
        ('draft', 'Vázlat'),
        ('planned', 'Beosztva'),
        ('in_progress', 'Folyamatban'),
        ('completed', 'Kész'),
        ('cancelled', 'Törölve'),
        ('overdue', 'Késésben'),
    ]

    title = models.CharField("Munka neve", max_length=200)
    description = models.TextField("Leírás", blank=True)
    client_name = models.CharField("Ügyfél neve", max_length=200, blank=True)
    location = models.CharField("Helyszín", max_length=300, blank=True)
    estimated_hours = models.DecimalField(
        "Becsült munkaóra",
        max_digits=7,
        decimal_places=1,
        validators=[MinValueValidator(Decimal('0.5'))],
        help_text="A munka elvégzéséhez szükséges becsült idő órában."
    )
    remaining_hours = models.DecimalField(
        "Hátralévő munkaóra",
        max_digits=7,
        decimal_places=1,
        default=0,
        help_text="Automatikusan számolódik a beosztás alapján."
    )
    deadline = models.DateField("Határidő", null=True, blank=True)
    earliest_start_date = models.DateField("Legkorábbi kezdés", null=True, blank=True)
    priority = models.CharField(
        "Prioritás",
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='medium'
    )
    status = models.CharField(
        "Státusz",
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )
    created_at = models.DateTimeField("Létrehozva", auto_now_add=True)
    updated_at = models.DateTimeField("Módosítva", auto_now=True)

    class Meta:
        verbose_name = "Munka"
        verbose_name_plural = "Munkák"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} — {self.client_name or 'Névtelen'} ({self.estimated_hours} óra)"

    @property
    def scheduled_hours(self):
        """A már beosztott órák összege."""
        result = self.schedules.aggregate(
            total=models.Sum('hours')
        )['total']
        return float(result) if result else 0

    @property
    def is_fully_scheduled(self):
        """Minden óra be van-e osztva."""
        return self.remaining_hours <= 0

    @property
    def progress_percent(self):
        """Teljesítettség százalékban."""
        if self.estimated_hours and float(self.estimated_hours) > 0:
            scheduled = self.scheduled_hours
            return min(100, round((scheduled / float(self.estimated_hours)) * 100))
        return 0


class WorkSchedule(models.Model):
    """Naptárba tett munkaidő-blokk — egy adott munkából mikor mennyit végzel."""
    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name='schedules',
        verbose_name="Munka"
    )
    start_datetime = models.DateTimeField("Kezdés")
    end_datetime = models.DateTimeField("Befejezés")
    hours = models.DecimalField(
        "Óra",
        max_digits=5,
        decimal_places=1,
        help_text="A blokk hossza órában."
    )
    note = models.CharField("Megjegyzés", max_length=200, blank=True)
    is_auto_scheduled = models.BooleanField("Automatikus beosztás", default=False)
    created_at = models.DateTimeField("Létrehozva", auto_now_add=True)
    updated_at = models.DateTimeField("Módosítva", auto_now=True)

    class Meta:
        verbose_name = "Beosztás"
        verbose_name_plural = "Beosztások"
        ordering = ['start_datetime']

    def __str__(self):
        return f"{self.job.title}: {self.start_datetime:%Y-%m-%d %H:%M} – {self.end_datetime:%H:%M} ({self.hours} óra)"

    def save(self, *args, **kwargs):
        """Mentés előtt automatikusan számoljuk az órákat."""
        if self.start_datetime and self.end_datetime:
            delta = self.end_datetime - self.start_datetime
            self.hours = round(delta.total_seconds() / 3600, 1)
        super().save(*args, **kwargs)


class TimeOff(models.Model):
    """Tiltott időszak — szabadság, ünnep, magánprogram, esős nap stb."""
    title = models.CharField("Megnevezés", max_length=200)
    start_datetime = models.DateTimeField("Kezdés")
    end_datetime = models.DateTimeField("Befejezés")
    reason = models.CharField("Ok", max_length=200, blank=True,
                              help_text="Pl. szabadság, ünnepnap, esőnap, magánprogram")
    created_at = models.DateTimeField("Létrehozva", auto_now_add=True)

    class Meta:
        verbose_name = "Tiltott időszak"
        verbose_name_plural = "Tiltott időszakok"
        ordering = ['start_datetime']

    def __str__(self):
        return f"{self.title}: {self.start_datetime:%Y-%m-%d %H:%M} – {self.end_datetime:%H:%M}"


class Settings(models.Model):
    """
    Általános beállítások — egyetlen rekord.
    Az alkalmazás ebből olvassa ki a munkaidő kereteket, ebédszünetet, stb.
    Az admin felületen csak ezt az egy rekordot szabad szerkeszteni.
    """
    workday_start = models.TimeField("Munkanap kezdete", default='08:00')
    workday_end = models.TimeField("Munkanap vége", default='16:00')
    lunch_break_start = models.TimeField("Ebédszünet kezdete", default='12:00')
    lunch_break_end = models.TimeField("Ebédszünet vége", default='12:30')
    default_daily_hours = models.DecimalField(
        "Alap napi munkaóra",
        max_digits=4,
        decimal_places=1,
        default=8.0,
        validators=[MinValueValidator(Decimal('1')), MaxValueValidator(Decimal('16'))]
    )
    max_daily_hours = models.DecimalField(
        "Maximum napi munkaóra",
        max_digits=4,
        decimal_places=1,
        default=10.0,
        validators=[MinValueValidator(Decimal('1')), MaxValueValidator(Decimal('16'))],
        help_text="Ennél többet egy napra nem oszt be a rendszer."
    )
    min_schedule_block_hours = models.DecimalField(
        "Minimum beosztható blokk (óra)",
        max_digits=3,
        decimal_places=1,
        default=0.5,
        validators=[MinValueValidator(Decimal('0.5'))]
    )
    allow_weekend = models.BooleanField("Hétvégi munka engedélyezése", default=False)
    mon_active = models.BooleanField("Hétfő", default=True)
    tue_active = models.BooleanField("Kedd", default=True)
    wed_active = models.BooleanField("Szerda", default=True)
    thu_active = models.BooleanField("Csütörtök", default=True)
    fri_active = models.BooleanField("Péntek", default=True)
    sat_active = models.BooleanField("Szombat", default=False)
    sun_active = models.BooleanField("Vasárnap", default=False)

    class Meta:
        verbose_name = "Beállítás"
        verbose_name_plural = "Beállítások"

    def __str__(self):
        return f"Beállítások ({self.workday_start:%H:%M}–{self.workday_end:%H:%M}, {self.default_daily_hours} ó/nap)"

    def save(self, *args, **kwargs):
        """Csak egy rekord lehet."""
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        """Beállítások betöltése (ha nincs, létrehozza az alapértelmezettet)."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def is_workday(self, date):
        """Igaz-e, hogy az adott nap munkanap."""
        weekday_map = {
            0: self.mon_active,
            1: self.tue_active,
            2: self.wed_active,
            3: self.thu_active,
            4: self.fri_active,
            5: self.sat_active,
            6: self.sun_active,
        }
        return weekday_map.get(date.weekday(), False)
