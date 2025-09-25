# citas/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # --- Autenticación y navegación principal ---
    path('', views.inicio, name='inicio'),
    path('registro/', views.registro_view, name='registro'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),  # Redirige según el rol

    # --- Dashboards por rol ---
    path('dashboard/administradora/', views.dashboard_administradora, name='dashboard_administradora'),
    path('dashboard/enfermera/', views.dashboard_enfermera, name='dashboard_enfermera'),
    path('dashboard/doctor/', views.dashboard_doctor, name='dashboard_doctor'),

    # --- Gestión de Citas (Administradora) ---
    path('agendar-paciente/', views.agendar_paciente, name='agendar_paciente'),
    path('agendar-cita/', views.agendar_cita, name='agendar_cita'),
    path('citas/lista/', views.dashboard_citas, name='dashboard_citas'),
    path('citas/modificar/<int:cita_id>/', views.modificar_cita, name='modificar_cita'),
    path('citas/cancelar/<int:cita_id>/', views.cancelar_cita, name='cancelar_cita'),

    # --- Enfermera ---
    path('enfermera/signos-vitales/<int:cita_id>/', views.registrar_signos_vitales, name='registrar_signos_vitales'),

    # --- Doctor ---
    path('dashboard/doctor/cita/<int:cita_id>/', views.detalle_cita_doctor, name='detalle_cita_doctor'),
    path('dashboard/doctor/cita/<int:cita_id>/receta/', views.crear_receta, name='crear_receta'),
]
