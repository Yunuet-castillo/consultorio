# citas/urls.py
from django.urls import path
from . import views
from .views import RegisterAPIView, LoginAPIView, CitasListAPIView, SignosVitalesCreateAPIView

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
    path('dashboard/doctor/cita/<int:cita_id>/diagnostico/', views.realizar_diagnostico, name='realizar_diagnostico'),
    path('dashboard/doctor/cita/<int:cita_id>/receta/', views.agregar_receta, name='crear_receta'),

    # --- Mis citas ---
    #path('mis-citas/', views.mis_citas, name='mis_citas'),
    #path('detalle-cita/<int:cita_id>/', views.detalle_cita, name='detalle_cita'),
    #m path('dashboard/doctor/cita/<int:cita_id>/receta/', views.agregar_receta, name='crear_receta'),


    path('dashboard/doctor/cita/<int:cita_id>/', views.detalle_cita_doctor, name='detalle_cita_doctor'),
    path('dashboard/doctor/cita/<int:cita_id>/diagnostico/', views.realizar_diagnostico, name='realizar_diagnostico'),
    path('dashboard/doctor/cita/<int:cita_id>/receta/', views.agregar_receta, name='agregar_receta'),
    path('dashboard/doctor/cita/<int:cita_id>/receta/pdf/', views.generar_receta_pdf, name='generar_receta_pdf'),
    path('paciente/<int:paciente_id>/', views.detalle_paciente, name='detalle_paciente'),
    path("dashboard/doctor/", views.dashboard_doctor, name="dashboard_doctor"),
   # path("buscar_pacientes/", views.buscar_pacientes, name="buscar_pacientes"),
    path('buscar_pacientes/', views.buscar_pacientes_doctor, name='buscar_pacientes_doctor'),

    #path("buscar_pacientes/", views.buscar_pacientes, name="buscar_pacientes"),
    path("paciente/<int:paciente_id>/", views.detalle_paciente, name="detalle_paciente"),

        path('reporte-dia/', views.reporte_dia, name='reporte_dia'),
    path('reporte-semana/', views.reporte_semana, name='reporte_semana'),
    path('reporte-mes/', views.reporte_mes, name='reporte_mes'),



    #---------------------------
    # --- API REST con DRF ---  


    path('api/register/', RegisterAPIView.as_view(), name='api-register'),
    path('api/login/', LoginAPIView.as_view(), name='api-login'),
    path('api/citas/', CitasListAPIView.as_view(), name='api-citas'),
    path('api/signos/', SignosVitalesCreateAPIView.as_view(), name='api-signos'),
    path('citas/', CitasListAPIView.as_view(), name='citas-list'),
    path('agendar-cita/', views.agendar_cita, name='agendar_cita'),
    path('agendar-paciente/', views.agendar_paciente, name='agendar_paciente'),
    path('agendar-cita/<int:paciente_id>/', views.agendar_cita, name='agendar_cita'),
    path('doctor/dashboard/', views.dashboard_doctor, name='doctor_dashboard'),
    path('agendar/<int:paciente_id>/', views.agendar_paciente_existente, name='agendar_paciente_existente'),

path('pacientes/buscar/', views.buscar_pacientes_doctor, name='buscar_pacientes_doctor'),

path('doctor/paciente/<int:paciente_id>/agregar_estudio/', views.agregar_estudio, name='agregar_estudio'),
path('doctor/cita/<int:cita_id>/imprimir_historial/', views.imprimir_historial, name='imprimir_historial'),
path('dashboard/doctor/cita/<int:cita_id>/', views.detalle_cita_doctor, name='detalle_cita_doctor'),
 #path('api/citas/<int:doctor_id>/', views.citas_por_doctor),
]