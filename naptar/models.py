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
            if delta.total_seconds() <= 0:
                raise ValueError(
                    f"A befejezés ({self.end_datetime}) nem lehet a kezdés "
                    f"({self.start_datetime}) előtt vagy azzal egyenlő."
                )
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


class DayOverride(models.Model):
    """
    Egyedi nap felülbírálás — konkrét dátumra eltérő munkaidő.
    Ha egy napra létezik DayOverride, a scheduler ezt használja a heti beállítás helyett.
    """
    date = models.DateField("Dátum", unique=True)
    is_workday = models.BooleanField("Munkanap", default=True)
    start_time = models.TimeField("Kezdés", null=True, blank=True)
    end_time = models.TimeField("Befejezés", null=True, blank=True)
    note = models.CharField("Megjegyzés", max_length=200, blank=True)

    class Meta:
        verbose_name = "Egyedi nap"
        verbose_name_plural = "Egyedi napok"
        ordering = ['date']

    def __str__(self):
        if self.is_workday and self.start_time and self.end_time:
            return f"{self.date}: {self.start_time}–{self.end_time} ({self.note or 'munkanap'})"
        return f"{self.date}: {'szabadnap' if not self.is_workday else 'munkanap'}"


class Settings(models.Model):
    """
    Általános beállítások — egyetlen rekord.
    Minden napra külön beállítható, hogy dolgozol-e, és ha igen, mettől meddig.
    """
    # Hétfő
    mon_active = models.BooleanField("Hétfő", default=True)
    mon_start = models.TimeField("Hétfő kezdés", default='08:00', null=True, blank=True)
    mon_end = models.TimeField("Hétfő befejezés", default='16:00', null=True, blank=True)
    # Kedd
    tue_active = models.BooleanField("Kedd", default=True)
    tue_start = models.TimeField("Kedd kezdés", default='08:00', null=True, blank=True)
    tue_end = models.TimeField("Kedd befejezés", default='16:00', null=True, blank=True)
    # Szerda
    wed_active = models.BooleanField("Szerda", default=True)
    wed_start = models.TimeField("Szerda kezdés", default='08:00', null=True, blank=True)
    wed_end = models.TimeField("Szerda befejezés", default='16:00', null=True, blank=True)
    # Csütörtök
    thu_active = models.BooleanField("Csütörtök", default=True)
    thu_start = models.TimeField("Csütörtök kezdés", default='08:00', null=True, blank=True)
    thu_end = models.TimeField("Csütörtök befejezés", default='16:00', null=True, blank=True)
    # Péntek
    fri_active = models.BooleanField("Péntek", default=True)
    fri_start = models.TimeField("Péntek kezdés", default='08:00', null=True, blank=True)
    fri_end = models.TimeField("Péntek befejezés", default='16:00', null=True, blank=True)
    # Szombat
    sat_active = models.BooleanField("Szombat", default=False)
    sat_start = models.TimeField("Szombat kezdés", default='08:00', null=True, blank=True)
    sat_end = models.TimeField("Szombat befejezés", default='14:00', null=True, blank=True)
    # Vasárnap
    sun_active = models.BooleanField("Vasárnap", default=False)
    sun_start = models.TimeField("Vasárnap kezdés", default='08:00', null=True, blank=True)
    sun_end = models.TimeField("Vasárnap befejezés", default='14:00', null=True, blank=True)

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

    class Meta:
        verbose_name = "Beállítás"
        verbose_name_plural = "Beállítások"

    def __str__(self):
        return f"Beállítások (hétfő–péntek: {self.mon_start}–{self.mon_end}, max {self.max_daily_hours} ó/nap)"

    def save(self, *args, **kwargs):
        """Csak egy rekord lehet."""
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        """Beállítások betöltése (ha nincs, létrehozza az alapértelmezettet)."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    # Napi mezők mapje: (active_attr, start_attr, end_attr)
    _DAY_MAP = {
        0: ('mon_active', 'mon_start', 'mon_end'),
        1: ('tue_active', 'tue_start', 'tue_end'),
        2: ('wed_active', 'wed_start', 'wed_end'),
        3: ('thu_active', 'thu_start', 'thu_end'),
        4: ('fri_active', 'fri_start', 'fri_end'),
        5: ('sat_active', 'sat_start', 'sat_end'),
        6: ('sun_active', 'sun_start', 'sun_end'),
    }

    def is_workday(self, date):
        """Igaz-e, hogy az adott nap munkanap."""
        if date.weekday() not in self._DAY_MAP:
            return False
        active_attr, _, _ = self._DAY_MAP[date.weekday()]
        return getattr(self, active_attr, False)

    def get_day_hours(self, date):
        """Visszaadja az adott nap munkaidejét (start, end) vagy (None, None)-t."""
        if not self.is_workday(date):
            return None, None
        _, start_attr, end_attr = self._DAY_MAP[date.weekday()]
        return getattr(self, start_attr), getattr(self, end_attr)
