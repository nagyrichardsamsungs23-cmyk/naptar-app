"""
Naptár Alkalmazás — View-k
===========================
Magyar nyelvű építőipari munkaidő-tervező naptár.
"""

import json
from datetime import date, datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseBadRequest
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import AuthenticationForm
from django.db.models import Sum
from decimal import Decimal

from .models import Job, WorkSchedule, TimeOff, Settings, DayOverride
from .scheduler import schedule_job, get_free_slots_summary


# ============================================================
#  BEJELENTKEZÉS
# ============================================================

def login_view(request):
    """Bejelentkezési oldal."""
    if request.user.is_authenticated:
        return redirect('calendar')
    
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            next_url = request.GET.get('next', 'calendar')
            return redirect(next_url)
    else:
        form = AuthenticationForm()
    
    return render(request, 'naptar/login.html', {'form': form})


def logout_view(request):
    """Kijelentkezés."""
    logout(request)
    return redirect('login')


# ============================================================
#  FŐ OLDALAK
# ============================================================

@login_required
def calendar_view(request):
    """Naptár oldal — FullCalendar integrációval."""
    jobs = Job.objects.exclude(status__in=['cancelled']).order_by('-created_at')
    statuses = Job.STATUS_CHOICES
    return render(request, 'naptar/calendar.html', {
        'jobs': jobs,
        'statuses': dict(statuses),
        'page': 'calendar',
    })


@login_required
def dashboard(request):
    """Admin dashboard — áttekintő statisztikákkal."""
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    month_end = today + timedelta(days=30)
    
    # Alap statisztikák
    active_jobs = Job.objects.exclude(status__in=['completed', 'cancelled'])
    today_schedules = WorkSchedule.objects.filter(
        start_datetime__date=today
    ).order_by('start_datetime')
    
    deadline_jobs = Job.objects.filter(
        deadline__isnull=False,
        deadline__lte=month_end,
    ).exclude(status__in=['completed', 'cancelled']).order_by('deadline')
    
    # Heti terhelés
    week_schedules = WorkSchedule.objects.filter(
        start_datetime__date__gte=week_start,
        start_datetime__date__lte=week_end,
    )
    weekly_hours = week_schedules.aggregate(total=Sum('hours'))['total'] or 0
    
    # Szabad órák a következő 30 napban
    free_slots = get_free_slots_summary(today, month_end)
    
    context = {
        'page': 'dashboard',
        'active_jobs_count': active_jobs.count(),
        'today_schedules': today_schedules,
        'today_hours': sum(float(s.hours) for s in today_schedules),
        'weekly_hours': float(weekly_hours),
        'deadline_jobs': deadline_jobs[:10],
        'free_hours_next_30_days': free_slots['total_hours'],
        'jobs_in_progress': active_jobs.filter(status='in_progress').count(),
        'jobs_planned': active_jobs.filter(status='planned').count(),
        'jobs_overdue': active_jobs.filter(status='overdue').count(),
    }
    return render(request, 'naptar/dashboard.html', context)


# ============================================================
#  MUNKA CRUD
# ============================================================

@login_required
def job_create(request):
    """Új munka létrehozása."""
    if request.method == 'POST':
        job = Job(
            title=request.POST.get('title', ''),
            description=request.POST.get('description', ''),
            client_name=request.POST.get('client_name', ''),
            location=request.POST.get('location', ''),
            estimated_hours=Decimal(request.POST.get('estimated_hours', '0') or '0'),
            earliest_start_date=request.POST.get('earliest_start_date') or None,
            deadline=request.POST.get('deadline') or None,
            priority=request.POST.get('priority', 'medium'),
            status='draft',
        )
        # Dátum validáció
        if job.earliest_start_date and job.deadline and job.earliest_start_date > job.deadline:
            return render(request, 'naptar/job_form.html', {
                'page': 'job_create',
                'job': None,
                'statuses': Job.STATUS_CHOICES,
                'priorities': Job.PRIORITY_CHOICES,
                'error': 'A kezdő dátum nem lehet a határidő után.',
            })
        
        # remaining_hours = estimated_hours kezdetben
        job.remaining_hours = job.estimated_hours
        job.save()
        
        # Automatikus beosztás?
        if request.POST.get('auto_schedule') == 'yes' and float(job.estimated_hours) > 0:
            schedule_job(job)
        
        return redirect('calendar')
    
    return render(request, 'naptar/job_form.html', {
        'page': 'job_create',
        'job': None,
        'statuses': Job.STATUS_CHOICES,
        'priorities': Job.PRIORITY_CHOICES,
    })


@login_required
def job_edit(request, job_id):
    """Munka szerkesztése."""
    job = get_object_or_404(Job, id=job_id)
    
    if request.method == 'POST':
        job.title = request.POST.get('title', job.title)
        job.description = request.POST.get('description', job.description)
        job.client_name = request.POST.get('client_name', job.client_name)
        job.location = request.POST.get('location', job.location)
        job.estimated_hours = Decimal(request.POST.get('estimated_hours', '0') or '0')
        job.earliest_start_date = request.POST.get('earliest_start_date') or None
        job.deadline = request.POST.get('deadline') or None
        job.priority = request.POST.get('priority', job.priority)
        job.status = request.POST.get('status', job.status)
        job.save()
        return redirect('calendar')
    
    return render(request, 'naptar/job_form.html', {
        'page': 'job_edit',
        'job': job,
        'statuses': Job.STATUS_CHOICES,
        'priorities': Job.PRIORITY_CHOICES,
    })


@login_required
def job_delete(request, job_id):
    """Munka törlése."""
    job = get_object_or_404(Job, id=job_id)
    if request.method == 'POST':
        job.delete()
        return redirect('calendar')
    return render(request, 'naptar/job_delete.html', {'job': job})


# ============================================================
#  BEOSZTÁS MŰVELETEK
# ============================================================

@login_required
def job_schedule(request, job_id):
    """Automatikus beosztás indítása."""
    job = get_object_or_404(Job, id=job_id)
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Csak POST metódus'})
    
    result = schedule_job(job)
    return JsonResponse(result)


@login_required
def job_reschedule(request, job_id):
    """Munka teljes újraütemezése (régi automatikus beosztások törlése után)."""
    job = get_object_or_404(Job, id=job_id)
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Csak POST metódus'})
    
    # Összes automatikus beosztás törlése és újra
    result = schedule_job(job)
    return JsonResponse(result)


# ============================================================
#  API VÉGPONTOK (FullCalendar + AJAX)
# ============================================================

@login_required
def api_events(request):
    """
    FullCalendar események JSON-ben.
    GET paraméterek: start, end (ISO dátumok)
    Visszaadja a beosztásokat és a tiltott időszakokat.
    """
    start_str = request.GET.get('start', '')
    end_str = request.GET.get('end', '')
    
    events = []
    
    # Beosztások (WorkSchedule)
    schedules = WorkSchedule.objects.select_related('job').all()
    if start_str:
        schedules = schedules.filter(start_datetime__gte=start_str)
    if end_str:
        schedules = schedules.filter(end_datetime__lte=end_str)
    
    for s in schedules:
        color = _get_job_color(s.job)
        events.append({
            'id': f'sched_{s.id}',
            'title': f'{s.job.title} ({s.hours}ó)',
            'start': s.start_datetime.isoformat(),
            'end': s.end_datetime.isoformat(),
            'color': color,
            'textColor': '#fff',
            'extendedProps': {
                'type': 'schedule',
                'schedule_id': s.id,
                'job_id': s.job.id,
                'job_title': s.job.title,
                'client': s.job.client_name,
                'location': s.job.location,
                'hours': float(s.hours),
                'status': s.job.status,
                'is_auto_scheduled': s.is_auto_scheduled,
            }
        })
    
    # Tiltott időszakok (TimeOff)
    timeoffs = TimeOff.objects.all()
    if start_str:
        timeoffs = timeoffs.filter(start_datetime__gte=start_str)
    if end_str:
        timeoffs = timeoffs.filter(end_datetime__lte=end_str)
    
    for t in timeoffs:
        events.append({
            'id': f'off_{t.id}',
            'title': t.title,
            'start': t.start_datetime.isoformat(),
            'end': t.end_datetime.isoformat(),
            'color': '#9ca3af',
            'textColor': '#1f2937',
            'display': 'background',
            'extendedProps': {
                'type': 'timeoff',
                'timeoff_id': t.id,
                'reason': t.reason,
            }
        })
    
    return JsonResponse(events, safe=False)


def _get_job_color(job):
    """Visszaadja a munka státuszához tartozó színt."""
    colors = {
        'draft': '#6b7280',        # szürke
        'planned': '#3b82f6',      # kék
        'in_progress': '#f59e0b',  # narancs
        'completed': '#10b981',    # zöld
        'cancelled': '#ef4444',    # piros
        'overdue': '#dc2626',      # sötét piros
    }
    return colors.get(job.status, '#3b82f6')


@login_required
def api_free_slots(request):
    """Szabad idősávok lekérése adott intervallumban."""
    today = date.today()
    end_date = today + timedelta(days=30)
    
    start_str = request.GET.get('start', today.isoformat())
    end_str = request.GET.get('end', end_date.isoformat())
    
    try:
        from_date = datetime.strptime(start_str, '%Y-%m-%d').date()
        to_date = datetime.strptime(end_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': 'Hibás dátum formátum'}, status=400)
    
    summary = get_free_slots_summary(from_date, to_date)
    return JsonResponse(summary)


@login_required
def api_event_move(request, event_id):
    """
    Naptárban húzott esemény (drop) mentése.
    FullCalendar eventDrop callback-ből hívva.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False})
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Hibás JSON'})
    
    # Az event_id formátuma: sched_X
    if not event_id.startswith('sched_'):
        return JsonResponse({'success': False, 'error': 'Csak beosztás mozgatható'})
    
    schedule_id = int(event_id.replace('sched_', ''))
    schedule = get_object_or_404(WorkSchedule, id=schedule_id)
    
    new_start = data.get('start')
    new_end = data.get('end')
    
    if new_start:
        schedule.start_datetime = new_start
        schedule.is_auto_scheduled = False  # Kézi módosítás
    if new_end:
        schedule.end_datetime = new_end
        schedule.is_auto_scheduled = False
    
    ok, err = _check_overlap(schedule, schedule.start_datetime, schedule.end_datetime)
    if not ok:
        return JsonResponse({'success': False, 'error': err})
    
    try:
        schedule.save()
    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)})
    
    # Frissítsük a munka remaining_hours értékét
    _update_job_remaining(schedule.job)
    
    return JsonResponse({'success': True, 'hours': float(schedule.hours)})


@login_required
def api_event_resize(request, event_id):
    """
    Időtartam módosítás (resize) mentése.
    FullCalendar eventResize callback-ből hívva.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False})
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Hibás JSON'})
    
    if not event_id.startswith('sched_'):
        return JsonResponse({'success': False, 'error': 'Csak beosztás méretezhető'})
    
    schedule_id = int(event_id.replace('sched_', ''))
    schedule = get_object_or_404(WorkSchedule, id=schedule_id)
    
    new_end = data.get('end')
    if new_end:
        schedule.end_datetime = new_end
        schedule.is_auto_scheduled = False
        
        ok, err = _check_overlap(schedule, schedule.start_datetime, schedule.end_datetime)
        if not ok:
            return JsonResponse({'success': False, 'error': err})
        
        try:
            schedule.save()
        except ValueError as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    _update_job_remaining(schedule.job)
    
    return JsonResponse({'success': True, 'hours': float(schedule.hours)})


@login_required
def api_event_delete(request, event_id):
    """Esemény törlése."""
    if request.method != 'DELETE' and request.method != 'POST':
        return JsonResponse({'success': False})
    
    if event_id.startswith('sched_'):
        schedule_id = int(event_id.replace('sched_', ''))
        schedule = get_object_or_404(WorkSchedule, id=schedule_id)
        job = schedule.job
        schedule.delete()
        _update_job_remaining(job)
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False, 'error': 'Ismeretlen esemény típus'})


def _update_job_remaining(job):
    """Frissíti a munka remaining_hours mezőjét a beosztások alapján."""
    total_scheduled = job.schedules.aggregate(
        total=Sum('hours')
    )['total'] or 0
    job.remaining_hours = max(0, float(job.estimated_hours) - float(total_scheduled))
    job.save(update_fields=['remaining_hours', 'updated_at'])


def _check_overlap(schedule, new_start, new_end):
    """Ellenőrzi, hogy az új idősáv nem ütközik-e más beosztással
    vagy tiltott időszakkal. Visszaad (ok: bool, error_msg: str|None)."""
    overlapping_schedules = WorkSchedule.objects.filter(
        start_datetime__lt=new_end,
        end_datetime__gt=new_start,
    ).exclude(id=schedule.id)

    if overlapping_schedules.exists():
        return False, 'Az idősáv ütközik egy másik beosztással.'

    overlapping_timeoffs = TimeOff.objects.filter(
        start_datetime__lt=new_end,
        end_datetime__gt=new_start,
    )

    if overlapping_timeoffs.exists():
        return False, 'Az idősáv tiltott időszakba esik.'

    return True, None


# ============================================================
#  BEÁLLÍTÁSOK
# ============================================================

@login_required
def settings_view(request):
    """Beállítások oldal."""
    settings_obj = Settings.load()
    
    if request.method == 'POST':
        action = request.POST.get('action', '')
        
        # Egyedi nap törlése
        if action == 'delete_override':
            override_id = request.POST.get('override_id')
            DayOverride.objects.filter(id=override_id).delete()
            return redirect('settings')
        
        # Egyedi nap hozzáadása
        if action == 'add_override':
            override_date = request.POST.get('override_date', '')
            is_workday = request.POST.get('override_workday') == 'on'
            start_time = request.POST.get('override_start', '') or None
            end_time = request.POST.get('override_end', '') or None
            note = request.POST.get('override_note', '')
            
            if override_date:
                # Meglévő frissítése vagy új létrehozása
                override, _ = DayOverride.objects.update_or_create(
                    date=override_date,
                    defaults={
                        'is_workday': is_workday,
                        'start_time': start_time,
                        'end_time': end_time,
                        'note': note,
                    }
                )
            return redirect('settings')
        
        # Heti beállítások mentése
        for day in ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']:
            setattr(settings_obj, f'{day}_active', request.POST.get(f'{day}_active') == 'on')
            start_val = request.POST.get(f'{day}_start', '')
            end_val = request.POST.get(f'{day}_end', '')
            if start_val:
                setattr(settings_obj, f'{day}_start', start_val)
            if end_val:
                setattr(settings_obj, f'{day}_end', end_val)
        
        settings_obj.max_daily_hours = Decimal(request.POST.get('max_daily_hours', '10') or '10')
        settings_obj.min_schedule_block_hours = Decimal(request.POST.get('min_schedule_block_hours', '0.5') or '0.5')
        
        settings_obj.save()
        return redirect('settings')
    
    # Egyedi napok listája (következő 60 nap)
    overrides = DayOverride.objects.filter(
        date__gte=date.today()
    ).order_by('date')[:90]
    
    return render(request, 'naptar/settings.html', {
        'page': 'settings',
        'settings': settings_obj,
        'overrides': overrides,
    })
