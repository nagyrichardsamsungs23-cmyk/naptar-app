"""
Naptár Alkalmazás — Automatikus Beosztó Motor
==============================================
Minden napra külön beállítható munkaidő-ablakkal, ebédszünet nélkül.
"""

from datetime import datetime, timedelta, date, time
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum
from .models import Job, WorkSchedule, TimeOff, Settings, DayOverride


def get_available_slots(from_date, to_date):
    """
    Visszaadja az összes szabad idősávot két dátum között.
    
    Figyelembe veszi:
    - Naponkénti beállításokat (minden napra külön kezdés/vége)
    - Már meglévő beosztásokat (WorkSchedule)
    - Tiltott időszakokat (TimeOff)
    - Napi maximum munkaórát
    
    Vissza: [(start_dt, end_dt, available_minutes), ...]
    """
    settings = Settings.load()
    max_daily_minutes = int(float(settings.max_daily_hours) * 60)
    
    slots = []
    current_date = from_date
    
    while current_date <= to_date:
        # 1. Egyedi nap felülbírálás ellenőrzése
        override = DayOverride.objects.filter(date=current_date).first()
        if override:
            if not override.is_workday or not override.start_time or not override.end_time:
                current_date += timedelta(days=1)
                continue
            day_start = override.start_time
            day_end = override.end_time
        else:
            # 2. Heti beállítás
            day_start, day_end = settings.get_day_hours(current_date)
        
        if day_start is None or day_end is None:
            current_date += timedelta(days=1)
            continue
        
        # Aznapi munkaidő intervallum
        day_start_dt = timezone.make_aware(
            datetime.combine(current_date, day_start)
        )
        day_end_dt = timezone.make_aware(
            datetime.combine(current_date, day_end)
        )
        
        # Foglaltságok lekérése erre a napra
        busy_periods = _get_busy_periods(current_date)
        
        # Szabad blokkok kiszámítása
        free_blocks = _calculate_free_blocks(
            day_start_dt, day_end_dt, busy_periods, max_daily_minutes
        )
        
        slots.extend(free_blocks)
        current_date += timedelta(days=1)
    
    return slots


def _get_busy_periods(day_date):
    """
    Összegyűjti egy nap összes foglalt időszakát.
    Visszaad egy rendezett listát (start, end) tuple-ökből.
    """
    day_start = timezone.make_aware(datetime.combine(day_date, time.min))
    day_end = timezone.make_aware(datetime.combine(day_date, time.max))
    
    busy = []
    
    # Meglévő beosztások
    schedules = WorkSchedule.objects.filter(
        start_datetime__gte=day_start,
        start_datetime__lte=day_end
    ).order_by('start_datetime')
    
    for s in schedules:
        busy.append((s.start_datetime, s.end_datetime))
    
    # Tiltott időszakok
    timeoffs = TimeOff.objects.filter(
        start_datetime__lt=day_end,
        end_datetime__gt=day_start
    )
    
    for t in timeoffs:
        overlap_start = max(t.start_datetime, day_start)
        overlap_end = min(t.end_datetime, day_end)
        if overlap_start < overlap_end:
            busy.append((overlap_start, overlap_end))
    
    busy.sort(key=lambda x: x[0])
    return busy


def _calculate_free_blocks(day_start, day_end, busy_periods, max_daily_minutes):
    """
    A foglaltságok között kiszámolja a szabad blokkokat.
    Ebédszünet nélkül — egybefüggő munkaidő.
    """
    free_blocks = []
    current = day_start
    total_free_minutes = 0
    
    for busy_start, busy_end in busy_periods:
        if busy_start > current:
            free_minutes = (busy_start - current).total_seconds() / 60
            if free_minutes >= 30:
                remaining_daily = max_daily_minutes - total_free_minutes
                if remaining_daily > 0:
                    usable_minutes = min(free_minutes, remaining_daily)
                    free_blocks.append((current, busy_start, usable_minutes))
                    total_free_minutes += usable_minutes
        
        if busy_end > current:
            current = busy_end
        
        if total_free_minutes >= max_daily_minutes:
            break
    
    # Maradék idő a nap végéig
    if current < day_end and total_free_minutes < max_daily_minutes:
        free_minutes = (day_end - current).total_seconds() / 60
        if free_minutes >= 30:
            remaining_daily = max_daily_minutes - total_free_minutes
            usable_minutes = min(free_minutes, remaining_daily)
            free_blocks.append((current, day_end, usable_minutes))
    
    return free_blocks


def schedule_job(job):
    """
    Automatikusan beosztja a munkát a szabad idősávokba.
    
    Visszaad egy dict-et:
    {
        'success': True/False,
        'created_blocks': [...],
        'scheduled_hours': X.X,
        'missing_hours': X.X,
        'message': str
    }
    """
    settings = Settings.load()
    
    # Meglévő kézi (nem automatikus) beosztások összesítése
    manual = WorkSchedule.objects.filter(
        job=job, is_auto_scheduled=False
    ).aggregate(total=Sum('hours'))['total'] or 0
    manual_minutes = float(manual) * 60
    
    # Csak a manuálisan be NEM osztott órákat kell automatikusan beosztani
    required_minutes = max(0, float(job.estimated_hours) * 60 - manual_minutes)
    
    # Töröljük a korábbi automatikus beosztásokat
    WorkSchedule.objects.filter(job=job, is_auto_scheduled=True).delete()
    
    # Kezdő dátum meghatározása (biztosítjuk, hogy date objektum legyen)
    from_date = job.earliest_start_date if job.earliest_start_date else date.today()
    if isinstance(from_date, str):
        from_date = date.fromisoformat(from_date)
    deadline = job.deadline
    if isinstance(deadline, str):
        deadline = date.fromisoformat(deadline) if deadline else None
    to_date = deadline if deadline else from_date + timedelta(days=90)
    
    # Szabad idősávok lekérése
    available_slots = get_available_slots(from_date, to_date)
    
    created_blocks = []
    remaining_minutes = required_minutes
    min_block = float(settings.min_schedule_block_hours) * 60
    
    for slot_start, slot_end, slot_minutes in available_slots:
        if remaining_minutes <= 0:
            break
        
        if slot_minutes < min_block:
            continue
        
        used_minutes = min(remaining_minutes, slot_minutes)
        
        block_end = slot_start + timedelta(minutes=used_minutes)
        hours = round(used_minutes / 60, 1)
        
        schedule = WorkSchedule.objects.create(
            job=job,
            start_datetime=slot_start,
            end_datetime=block_end,
            hours=hours,
            is_auto_scheduled=True,
            note='Automatikus beosztás'
        )
        
        created_blocks.append({
            'id': schedule.id,
            'start': schedule.start_datetime.isoformat(),
            'end': schedule.end_datetime.isoformat(),
            'hours': hours,
        })
        
        remaining_minutes -= used_minutes
    
    # Hátralévő órák frissítése
    auto_hours = (required_minutes - remaining_minutes) / 60
    total_scheduled = float(manual) + auto_hours
    job.remaining_hours = max(0, float(job.estimated_hours) - total_scheduled)
    
    if remaining_minutes > 0 and job.remaining_hours > 0:
        missing_hours = round(job.remaining_hours, 1)
        # Csak akkor draft, ha tényleg van még be nem osztott óra
        if job.status not in ('in_progress', 'completed'):
            job.status = 'draft'
        job.save()
        return {
            'success': False,
            'created_blocks': created_blocks,
            'scheduled_hours': round(auto_hours, 1),
            'missing_hours': missing_hours,
            'message': (
                f"A munkához {job.estimated_hours} óra kell. "
                f"A megadott határidőig csak {total_scheduled:.1f} óra szabad. "
                f"Hiányzó idő: {missing_hours} óra."
            )
        }
    
    # Sikeres beosztás (vagy a kézi + automatikus együtt lefedi)
    if job.status not in ('in_progress', 'completed', 'cancelled'):
        job.status = 'planned'
    job.remaining_hours = max(0, float(job.estimated_hours) - total_scheduled)
    job.save()
    
    return {
        'success': True,
        'created_blocks': created_blocks,
        'scheduled_hours': round(auto_hours, 1),
        'missing_hours': 0,
        'message': f"A {job.estimated_hours} órás munka beosztása sikeres! {len(created_blocks)} blokkban."
    }


def get_free_slots_summary(from_date, to_date):
    """
    Visszaad egy összesítő dict-et a szabad idősávokról.
    """
    slots = get_available_slots(from_date, to_date)
    
    daily = {}
    total_minutes = 0
    
    for start, end, minutes in slots:
        day_key = start.strftime('%Y-%m-%d')
        if day_key not in daily:
            daily[day_key] = 0
        daily[day_key] += minutes
        total_minutes += minutes
    
    return {
        'total_hours': round(total_minutes / 60, 1),
        'daily_breakdown': {
            day: round(mins / 60, 1)
            for day, mins in sorted(daily.items())
        },
        'slot_count': len(slots),
    }
