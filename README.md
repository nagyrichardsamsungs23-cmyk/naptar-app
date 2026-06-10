# Naptár Alkalmazás — Építőipari munkaidő-tervező

Django alapú webalkalmazás építőipari munkák automatikus beosztásához.

## Funkciók

- **Naptár nézet** (FullCalendar): havi, heti, napi nézet, drag & drop
- **Dashboard**: áttekintő statisztikák, mai munkák, heti terhelés, közelgő határidők
- **Automatikus beosztó motor**: 
  - Szabad idősávok keresése
  - Munkaórák szétosztása több napra
  - Ebédszünet figyelembevétele
  - Napi maximum óra betartása
  - Tiltott időszakok kezelése
  - Ha nincs elég idő, figyelmeztet a hiányzó óraszámmal
- **Admin felület** (Django Admin): munkák, beosztások, tiltott időszakok kezelése
- **Beállítások**: munkaidő, ebédszünet, munkanapok testreszabása

## Tech stack

- Python 3.11+ / Django 5.2
- SQLite (fejlesztés) / PostgreSQL (éles)
- FullCalendar 6
- Bootstrap 5 + Bootstrap Icons
- Inter font
- Whitenoise (statikus fájlok)
- Gunicorn (production szerver)

## Telepítés

```bash
# 1. Virtuális környezet
cd "Naptár app"
python3 -m venv .venv
source .venv/bin/activate

# 2. Függőségek
pip install -r requirements.txt

# 3. Migráció
python manage.py migrate

# 4. Seed adatok (alapértelmezett beállítások)
python manage.py seed_data

# 5. Szuperuser létrehozása
python manage.py createsuperuser

# 6. Szerver indítása
python manage.py runserver
```

## Belépés

- **Weboldal**: http://localhost:8000
- **Admin felület**: http://localhost:8000/admin/
- **Alapértelmezett felhasználó** (ha seed_data-val jött létre): `admin` / `Admin1234`

## Használat

1. Jelentkezz be
2. Állítsd be a munkaidő kereteket: **Beállítások** menü
3. Hozz létre új munkát: **Új munka** menü
   - Ha bejelölöd az "Automatikus beosztás"-t, a rendszer azonnal beosztja
4. A naptárban látod a beosztásokat
5. Az eseményeket húzással mozgathatod, széthúzással módosíthatod az időtartamot
6. A **Dashboard** oldalon követheted a statisztikákat

## Projekt struktúra

```
Naptár app/
├── config/             # Django projekt beállítások
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── naptar/             # Fő alkalmazás
│   ├── models.py       # Job, WorkSchedule, TimeOff, Settings
│   ├── views.py        # Naptár, dashboard, API, CRUD
│   ├── admin.py        # Admin felület
│   ├── scheduler.py    # Automatikus beosztó motor
│   ├── urls.py
│   └── management/     # seed_data parancs
├── templates/
│   ├── base.html
│   └── naptar/
│       ├── login.html
│       ├── calendar.html
│       ├── dashboard.html
│       ├── job_form.html
│       ├── job_delete.html
│       └── settings.html
├── static/
│   └── css/style.css
├── manage.py
├── requirements.txt
└── railway.toml
```

## API végpontok

| Metódus | URL | Leírás |
|---|---|---|
| GET | /api/events/ | Naptár események (FullCalendar) |
| GET | /api/free-slots/ | Szabad idősávok |
| POST | /api/events/{id}/move/ | Esemény mozgatása |
| POST | /api/events/{id}/resize/ | Esemény átméretezése |
| POST | /api/events/{id}/delete/ | Esemény törlése |
| POST | /jobs/{id}/schedule/ | Automatikus beosztás |
| POST | /jobs/{id}/reschedule/ | Újratervezés |

## Railway deploy

A `railway.toml` tartalmazza a szükséges beállításokat. A deploy során automatikusan fut a `migrate` és a `seed_data`.

Környezeti változók Railway-en:
- `SECRET_KEY` — Django secret key
- `DEBUG=False`
- `DATABASE_URL` — PostgreSQL kapcsolat (automatikus a Railway Postgres pluginból)
- `ALLOWED_HOSTS` — a Railway domain
