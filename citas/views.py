from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import IntegrityError
from .forms import RegistroForm, LoginForm, PacienteForm, CitaForm, SignosVitalesForm, RecetaForm
from .models import CustomUser, Paciente, Cita, Doctor, SignosVitales, Receta
from datetime import date

# --- Página de inicio ---
def inicio(request):
    return render(request, 'inicio.html')


# --- Funciones de Redirección y Seguridad ---
def is_administradora(user):
    return user.is_authenticated and user.role.lower() == 'administradora'

def is_doctor(user):
    return user.is_authenticated and user.role.lower() == 'doctor'

def is_enfermera(user):
    return user.is_authenticated and user.role.lower() == 'enfermera'

def redirect_by_role(user):
    if user.role.lower() == 'administradora':
        return redirect('dashboard_administradora')
    elif user.role.lower() == 'enfermera':
        return redirect('dashboard_enfermera')
    elif user.role.lower() == 'doctor':
        return redirect('dashboard_doctor')
    return redirect('inicio')


# --- Vista genérica de dashboard ---
@login_required
def dashboard(request):
    citas_del_dia = None
    
    if request.user.is_authenticated:
        if request.user.role.lower() == 'administradora':
            citas_del_dia = Cita.objects.filter(fecha=date.today()).order_by('hora')
        elif request.user.role.lower() == 'doctor':
            doctor_instance, created = Doctor.objects.get_or_create(user=request.user)
            citas_del_dia = Cita.objects.filter(doctor=doctor_instance, fecha=date.today()).order_by('hora')
        elif request.user.role.lower() == 'enfermera':
            citas_del_dia = Cita.objects.filter(fecha=date.today()).order_by('hora')
    
    context = {
        'citas': citas_del_dia,
        'fecha_actual': date.today(),
    }
    return render(request, 'dashboard.html', context)


# --- Autenticación ---
def registro_view(request):
    if request.method == 'POST':
        form = RegistroForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, '¡Registro exitoso! Por favor, inicia sesión.')
                return redirect('login')
            except IntegrityError:
                messages.error(request, "Ya existe un usuario con esos datos.")
        else:
            messages.error(request, "Error en el registro. Por favor, revisa los datos.")
    else:
        form = RegistroForm()
    return render(request, 'registro.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            role = form.cleaned_data['role']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            if user is not None:
                if user.role.lower() == role.lower():
                    login(request, user)
                    messages.success(request, f"Bienvenido {user.get_full_name()} como {user.role}")

                    # ⚡ Crear perfil de doctor automáticamente si no existe
                    if user.role.lower() == 'doctor':
                        Doctor.objects.get_or_create(user=user)

                    return redirect_by_role(user)
                else:
                    messages.error(request, "El rol ingresado no coincide con tu cuenta.")
            else:
                messages.error(request, "Usuario o contraseña incorrectos.")
    else:
        form = LoginForm()
    return render(request, 'login.html', {'form': form})


@login_required
def logout_view(request):
    logout(request)
    messages.info(request, "Has cerrado sesión correctamente.")
    return redirect('login')


# --- Dashboards por Rol ---
@login_required
@user_passes_test(is_administradora)
def dashboard_administradora(request):
    citas = Cita.objects.all().order_by('fecha', 'hora')
    contexto = {
        'citas': citas,
        'fecha_actual': date.today(),
    }
    return render(request, 'recepcion/dashboard.html', contexto)


@login_required
@user_passes_test(is_doctor)
def dashboard_doctor(request):
    doctor = Doctor.objects.get(user=request.user)
    citas = Cita.objects.filter(doctor=doctor, fecha__gte=date.today()).order_by('fecha', 'hora')

    contexto = {
        'doctor': doctor,
        'citas': citas,
        'fecha_actual': date.today(),
    }
    return render(request, 'doctor/dashboard_doctor.html', contexto)


@login_required
@user_passes_test(is_enfermera)
def dashboard_enfermera(request):
    return render(request, 'dashboards/dashboard_enfermera.html')


# --- Gestión de Citas (Rol Administradora) ---
@login_required
@user_passes_test(is_administradora)
def agendar_paciente(request):
    if request.method == 'POST':
        paciente_form = PacienteForm(request.POST)
        if paciente_form.is_valid():
            paciente = paciente_form.save()
            request.session['paciente_id'] = paciente.id
            return redirect('agendar_cita')
        else:
            messages.error(request, "Error al registrar al paciente. Por favor, revisa los datos.")
    else:
        paciente_form = PacienteForm()
    
    contexto = {
        'paciente_form': paciente_form,
    }
    return render(request, 'recepcion/agendar_paciente.html', contexto)


@login_required
def agendar_cita(request):
    doctores = CustomUser.objects.filter(role=CustomUser.Roles.DOCTOR)
    if request.method == 'POST':
        form = CitaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '✅ La cita ha sido agendada con éxito.')
            return redirect('dashboard_administradora')
    else:
        form = CitaForm()
    
    context = {
        'form': form,
        'titulo': 'Agendar Cita',
        'boton': 'Agendar',
        'doctores': doctores,
    }
    return render(request, 'recepcion/agendar_cita.html', context)


@login_required
@user_passes_test(is_administradora)
def dashboard_citas(request):
    citas = Cita.objects.all().order_by('fecha', 'hora')
    contexto = {
        'citas': citas,
    }
    return render(request, 'recepcion/dashboard.html', contexto)


@login_required
@user_passes_test(is_administradora)
def modificar_cita(request, cita_id):
    cita = get_object_or_404(Cita, id=cita_id)

    if request.method == 'POST':
        form = CitaForm(request.POST, instance=cita)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Cita modificada exitosamente.")
            return redirect('dashboard_administradora')
        else:
            messages.error(request, "❌ Error al modificar la cita. Revisa los datos.")
    else:
        form = CitaForm(instance=cita)

    contexto = {
        'form': form,
        'titulo': "Modificar Cita",
        'boton': "Guardar Cambios",
    }
    return render(request, 'recepcion/agendar_cita.html', contexto)


@login_required
@user_passes_test(is_administradora)
def cancelar_cita(request, cita_id):
    cita = get_object_or_404(Cita, id=cita_id)
    if cita.estado != 'Cancelada':
        cita.estado = 'Cancelada'
        cita.save()
        messages.success(request, "✅ La cita ha sido cancelada exitosamente.")
    else:
        messages.info(request, "ℹ️ Esta cita ya estaba cancelada.")
    return redirect('dashboard_citas')


# --- Gestión de Signos Vitales (Rol Enfermera) ---
@login_required
@user_passes_test(is_enfermera)
def registrar_signos_vitales(request, cita_id):
    cita = get_object_or_404(Cita, id=cita_id)
    
    try:
        signos_vitales = SignosVitales.objects.get(cita=cita)
    except SignosVitales.DoesNotExist:
        signos_vitales = None

    if request.method == 'POST':
        form = SignosVitalesForm(request.POST, instance=signos_vitales)
        if form.is_valid():
            signos_vitales = form.save(commit=False)
            signos_vitales.cita = cita
            signos_vitales.save()
            messages.success(request, "✅ Signos vitales registrados exitosamente.")
            return redirect('dashboard_enfermera')
        else:
            messages.error(request, "❌ Error al registrar signos vitales.")
    else:
        form = SignosVitalesForm(instance=signos_vitales)

    contexto = {
        'form': form,
        'cita': cita,
    }
    return render(request, 'enfermera/registrar_signos_vitales.html', contexto)


# --- Gestión de Recetas y Diagnóstico (Rol Doctor) ---
@login_required
@user_passes_test(is_doctor)
def crear_receta(request, cita_id):
    cita = get_object_or_404(Cita, id=cita_id)
    
    if request.method == 'POST':
        form = RecetaForm(request.POST)
        if form.is_valid():
            receta = form.save(commit=False)
            receta.cita = cita
            receta.save()
            messages.success(request, "✅ Receta creada exitosamente.")
            return redirect('dashboard_doctor')
        else:
            messages.error(request, "❌ Error al crear la receta.")
    else:
        form = RecetaForm()
        
    contexto = {
        'form': form,
        'cita': cita,
    }
    return render(request, 'doctor/crear_receta.html', contexto)


@login_required
@user_passes_test(is_doctor)
def detalle_cita_doctor(request, cita_id):
    cita = get_object_or_404(Cita, id=cita_id)
    recetas = cita.recetas.all()
    
    contexto = {
        'cita': cita,
        'recetas': recetas,
    }
    return render(request, 'doctor/detalle_cita.html', contexto)
