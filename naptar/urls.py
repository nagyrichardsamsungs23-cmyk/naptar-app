from django.urls import path
from . import views

urlpatterns = [
    # Bejelentkezés
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Fő oldalak
    path('', views.calendar_view, name='calendar'),
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Munka CRUD
    path('jobs/create/', views.job_create, name='job_create'),
    path('jobs/<int:job_id>/edit/', views.job_edit, name='job_edit'),
    path('jobs/<int:job_id>/delete/', views.job_delete, name='job_delete'),
    
    # Beosztás
    path('jobs/<int:job_id>/schedule/', views.job_schedule, name='job_schedule'),
    path('jobs/<int:job_id>/reschedule/', views.job_reschedule, name='job_reschedule'),
    
    # API
    path('api/events/', views.api_events, name='api_events'),
    path('api/free-slots/', views.api_free_slots, name='api_free_slots'),
    path('api/events/<str:event_id>/move/', views.api_event_move, name='api_event_move'),
    path('api/events/<str:event_id>/resize/', views.api_event_resize, name='api_event_resize'),
    path('api/events/<str:event_id>/delete/', views.api_event_delete, name='api_event_delete'),
    
    # Beállítások
    path('settings/', views.settings_view, name='settings'),
]
