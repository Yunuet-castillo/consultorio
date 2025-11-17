
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import IntegrityError
from .forms import ( RegistroForm, LoginForm, PacienteForm, CitaForm, SignosVitalesForm, RecetaForm, DiagnosticoForm)
from .models import CustomUser, Paciente, Cita, Doctor, SignosVitales, Receta, Estudio
from datetime import date
from django.http import HttpResponse
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
import os
from django.conf import settings
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet

# ---------------------------
# --- Funciones de rol ---
# ---------------------------
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

# ---------------------------
# --- Página de inicio ---
# ---------------------------
def inicio(request):
    hoy = date.today()
    
    # Filtrar solo las citas del día actual
    citas = Cita.objects.filter(fecha=hoy).order_by('hora')
    
    # Contar las pendientes del día
    pendientes = citas.filter(estado='pendiente').count()
    
    contexto = {
        'citas': citas,
        'hoy': hoy, 
        'pendientes': pendientes
    }
    
    return render(request, 'inicio.html', contexto)

# ---------------------------
# --- Dashboard genérico ---
# ---------------------------
@login_required
def dashboard(request):
    citas_del_dia = None
    
    if request.user.role.lower() == 'administradora':
        citas_del_dia = Cita.objects.filter(fecha=date.today()).order_by('hora')
    elif request.user.role.lower() == 'doctor':
        doctor_instance, _ = Doctor.objects.get_or_create(user=request.user)
        citas_del_dia = Cita.objects.filter(doctor=doctor_instance, fecha=date.today()).order_by('hora')
    elif request.user.role.lower() == 'enfermera':
        citas_del_dia = Cita.objects.filter(fecha=date.today()).order_by('hora')
    
    context = {
        'citas': citas_del_dia,
        'fecha_actual': date.today(),
    }
    return render(request, 'dashboard.html', context)

# ---------------------------
# --- Registro y Login ---
# ---------------------------
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

                    # Crear perfil de doctor si no existe
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

# ---------------------------
# --- Dashboards por rol ---
# ---------------------------
from datetime import date
from django.db.models import Q
@login_required
@user_passes_test(is_administradora)
def dashboard_administradora(request):
    fecha_actual = date.today()
    citas = Cita.objects.filter(fecha__gte=fecha_actual).order_by('fecha', 'hora')
    resultado = None
    mensaje = None
    tab_activa = 'citas'

    if request.method == 'POST':
        buscar = request.POST.get('buscar', '').strip()
        paciente_id = request.POST.get('paciente_id')

        # Si se presionó "Agendar"
        if paciente_id:
            request.session['paciente_id'] = paciente_id
            return redirect('agendar_cita')

        # Si se realizó una búsqueda
        if buscar:
            resultado = Paciente.objects.filter(
                Q(nombre__icontains=buscar) |
                Q(apellido_paterno__icontains=buscar) |
                Q(apellido_materno__icontains=buscar) |
                Q(telefono__icontains=buscar) |
                Q(numero__icontains=buscar) |
                Q(id__icontains=buscar)
            )

            if not resultado.exists():
                mensaje = "⚠️ No se encontró ningún paciente con ese dato."

            tab_activa = 'buscar'

    contexto = {
        'citas': citas,
        'fecha_actual': fecha_actual,
        'resultado': resultado,
        'mensaje': mensaje,
        'tab_activa': tab_activa,
    }
    return render(request, 'recepcion/dashboard.html', contexto)



from .forms import EstudioForm
from PyPDF2 import PdfReader
from PIL import Image
import pytesseract

def leer_pdf(ruta):
    texto = ""
    with open(ruta, 'rb') as f:
        reader = PdfReader(f)
        for page in reader.pages:
            texto += page.extract_text() or ""
    return texto.strip()

def leer_imagen(ruta):
    imagen = Image.open(ruta)
    texto = pytesseract.image_to_string(imagen, lang='spa')
    return texto.strip()

def agregar_estudio(request, paciente_id):
    paciente = get_object_or_404(Paciente, id=paciente_id)

    if request.method == 'POST':
        form = EstudioForm(request.POST, request.FILES)
        if form.is_valid():
            estudio = form.save(commit=False)
            estudio.paciente = paciente
            estudio.save()

            ruta = estudio.archivo.path
            extension = os.path.splitext(ruta)[1].lower()
            texto_extraido = ""

            # Detectar tipo de archivo
            if extension in ['.pdf']:
                texto_extraido = leer_pdf(ruta)
            elif extension in ['.jpg', '.jpeg', '.png']:
                texto_extraido = leer_imagen(ruta)
            else:
                texto_extraido = "Tipo de archivo no compatible para lectura automática."

            estudio.texto_extraido = texto_extraido
            estudio.save()

            messages.success(request, 'Estudio agregado y leído correctamente.')
            return redirect('detalle_paciente', paciente_id=paciente.id)
    else:
        form = EstudioForm()

    return render(request, 'doctor/agregar_estudio.html', {'form': form, 'paciente': paciente})




# 🔧 Ruta típica de instalación (ajústala si es diferente)
def leer_imagen(ruta):
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = r"C:\Tesseract-OCR\tesseract.exe"

    imagen = Image.open(ruta)
    texto = pytesseract.image_to_string(imagen, lang='spa')
    return texto



from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Table, TableStyle
from .models import Cita, Estudio, SignosVitales

def imprimir_historial(request, cita_id):
    cita = get_object_or_404(Cita, id=cita_id)
    paciente = cita.paciente

    signos = SignosVitales.objects.filter(cita__paciente=paciente).order_by('-cita__fecha')
    estudios = Estudio.objects.filter(paciente=paciente).order_by('-fecha_subida')

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="historial_{paciente.nombre}.pdf"'

    p = canvas.Canvas(response, pagesize=letter)
    width, height = letter

    # -------------------------------
    # ENCABEZADO CON LOGO
    # -------------------------------
    try:
        logo = ImageReader("static/citas/img/logo.png")  # CAMBIA ESTA RUTA
        p.drawImage(logo, 40, height - 80, width=70, height=70, mask='auto')
    except:
        pass  # Si no hay logo, continúa sin él

    p.setFont("Helvetica-Bold", 16)
    p.drawString(130, height - 40, "Historial de Signos Vitales")

    p.setFont("Helvetica", 11)
    p.drawString(130, height - 60, f"Paciente: {paciente.nombre} {paciente.apellido_paterno} {paciente.apellido_materno or ''}")

    y = height - 110

    # -------------------------------------------------------
    # TABLA DE SIGNOS VITALES (ESTILO PROFESIONAL)
    # -------------------------------------------------------
    if signos.exists():
        p.setFont("Helvetica-Bold", 14)
        p.drawString(40, y, "Signos Vitales")
        y -= 20

        data = [
            ["Fecha", "Peso", "Presión", "Temp.", "Frec. Card.", "Frec. Resp.", "Oxígeno"]
        ]

        for s in signos:
            data.append([
                s.cita.fecha.strftime("%d/%m/%Y"),
                f"{s.peso} kg" if s.peso else "—",
                s.presion_arterial or "—",
                f"{s.temperatura} °C" if s.temperatura else "—",
                s.frecuencia_cardiaca or "—",
                s.frecuencia_respiratoria or "—",
                f"{s.saturacion_oxigeno}%" if s.saturacion_oxigeno else "—",
            ])

        tabla = Table(data, colWidths=[70, 55, 70, 50, 70, 70, 60])
        tabla.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.8, colors.grey),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
        ]))
        tabla.wrapOn(p, 40, y)
        tabla.drawOn(p, 40, y - (20 * len(data)))
        y -= (20 * len(data)) + 40
    else:
        p.drawString(40, y, "No hay signos vitales registrados.")
        y -= 40

    # -------------------------------------------------------
    # IMÁGENES DE ESTUDIOS (MÁS RECIENTES PRIMERO)
    # -------------------------------------------------------
    p.setFont("Helvetica-Bold", 14)
    p.drawString(40, y, "Estudios e Imágenes")
    y -= 25

    for estudio in estudios:
        p.setFont("Helvetica-Bold", 12)
        p.drawString(40, y, f"Estudio: {estudio.descripcion or 'Sin descripción'}")
        y -= 15

        p.setFont("Helvetica", 10)
        p.drawString(40, y, f"Fecha: {estudio.fecha_subida.strftime('%d/%m/%Y %H:%M')}")
        y -= 20

        try:
            img = ImageReader(estudio.archivo.path)
            p.drawImage(img, 40, y - 200, width=300, height=200, preserveAspectRatio=True, mask='auto')
            y -= 220
        except:
            p.drawString(40, y, "⚠ No se pudo cargar la imagen.")
            y -= 20

        if y < 120:
            p.showPage()
            y = height - 80

    # -------------------------
    # FINALIZAR PDF
    # -------------------------
    p.save()
    return response



@login_required
@user_passes_test(is_administradora)
def agendar_paciente_existente(request, paciente_id):
    # Guardar el paciente en sesión para usarlo en el formulario de agendar cita
    request.session['paciente_id'] = paciente_id
    return redirect('agendar_cita')



@login_required
@user_passes_test(is_doctor)
def dashboard_doctor(request):
    doctor = get_object_or_404(Doctor, user=request.user)
    citas = Cita.objects.filter(doctor=doctor, fecha__gte=date.today()).order_by('fecha', 'hora')
    contexto = {'doctor': doctor, 'citas': citas, 'fecha_actual': date.today()}
    return render(request, 'doctor/dashboard_doctor.html', contexto)

@login_required
@user_passes_test(is_enfermera)
def dashboard_enfermera(request):
    return render(request, 'dashboards/dashboard_enfermera.html')

# ---------------------------
# --- Gestión de Pacientes y Citas ---
# ---------------------------
# ---------------------------
# REGISTRO DEL PACIENTE
# ---------------------------
@login_required
@user_passes_test(is_administradora)
def agendar_paciente(request):
    if request.method == 'POST':
        paciente_form = PacienteForm(request.POST)
        if paciente_form.is_valid():
            paciente = paciente_form.save()
            # Guarda el ID del paciente en la sesión
            request.session['paciente_id'] = paciente.id
            return redirect('agendar_cita')
        else:
            messages.error(request, "Error al registrar al paciente. Por favor, revisa los datos.")
    else:
        paciente_form = PacienteForm()
    
    contexto = {'paciente_form': paciente_form}
    return render(request, 'recepcion/agendar_paciente.html', contexto)

# ---------------------------
# REGISTRO DE LA CITA (AUTOMÁTICO CON PACIENTE)
# ---------------------------
@login_required
def agendar_cita(request):
    paciente_id = request.session.get('paciente_id')
    paciente = None

    if paciente_id:
        from .models import Paciente, Doctor
        paciente = Paciente.objects.filter(id=paciente_id).first()
        doctores = Doctor.objects.all()
    else:
        doctores = Doctor.objects.all()

    if request.method == 'POST':
        # Pasamos paciente y doctor queryset al formulario
        form = CitaForm(request.POST, paciente=paciente)
        form.fields['doctor_user'].queryset = doctores

        if form.is_valid():
            form.save()
            messages.success(request, '✅ La cita ha sido agendada con éxito.')
            # Limpiar paciente de sesión
            if 'paciente_id' in request.session:
                request.session.pop('paciente_id')
            return redirect('dashboard_administradora')
        else:
            # Mostrar errores completos
            messages.error(request, form.errors.as_text())
    else:
        form = CitaForm(paciente=paciente)
        form.fields['doctor_user'].queryset = doctores

    context = {
        'form': form,
        'paciente': paciente,
        'titulo': 'Agendar Cita',
        'boton': 'Agendar',
    }
    return render(request, 'recepcion/agendar_cita.html', context)





# ---------------------------
# DASHBOARD
# ---------------------------
@login_required
@user_passes_test(is_administradora)
def dashboard_citas(request):
    citas = Cita.objects.all().order_by('fecha', 'hora')
    return render(request, 'recepcion/dashboard.html', {'citas': citas})

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

    contexto = {'form': form, 'titulo': "Modificar Cita", 'boton': "Guardar Cambios"}
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

# ---------------------------
# --- Gestión de Signos Vitales ---
# ---------------------------
@login_required
@user_passes_test(is_enfermera)
def registrar_signos_vitales(request, cita_id):
    cita = get_object_or_404(Cita, id=cita_id)
    signos_vitales = getattr(cita, 'signosvitales', None)
    
    if request.method == 'POST':
        form = SignosVitalesForm(request.POST, instance=signos_vitales)
        if form.is_valid():
            signos = form.save(commit=False)
            signos.cita = cita
            signos.save()
            messages.success(request, "✅ Signos vitales registrados exitosamente.")
            return redirect('dashboard_enfermera')
        else:
            messages.error(request, "❌ Error al registrar signos vitales.")
    else:
        form = SignosVitalesForm(instance=signos_vitales)

    contexto = {'form': form, 'cita': cita}
    return render(request, 'enfermera/registrar_signos_vitales.html', contexto)

# ---------------------------
# --- Gestión de Diagnóstico y Recetas ---
# ---------------------------
# ---------------------------
# Detalle de la cita para doctor
# ---------------------------
@login_required
@user_passes_test(is_doctor)
def detalle_cita_doctor(request, cita_id):
    
    # 1. Recuperar la Cita con precarga de 'paciente'.
    # Usamos get_object_or_404 para manejar si la Cita no existe.
    cita = get_object_or_404(
        # Incluimos 'paciente' en select_related, ya que esa relación (ForeignKey) siempre existe.
        Cita.objects.select_related('paciente'), 
        id=cita_id
    )
    
    # 2. Manejar relaciones inversas (SignosVitales y Receta)
    # Utilizamos getattr() para obtener el objeto. Si no existe, devuelve None en lugar
    # de lanzar la excepción citas.models.Cita.X.RelatedObjectDoesNotExist.
    
    signos = getattr(cita, 'signosvitales', None)
    receta = getattr(cita, 'receta', None) 
    contexto = {
        "cita": cita,
        "paciente": cita.paciente,
        "signos": signos, # Será un objeto SignosVitales o None
        "receta": receta  # Será un objeto Receta o None
    }
    
    # Asegúrate de que el template se llama "doctor/detalle_cita.html"
    return render(request, "doctor/detalle_cita.html", contexto)


# ---------------------------
# Realizar o editar diagnóstico
# ---------------------------
@login_required
@user_passes_test(is_doctor)
def realizar_diagnostico(request, cita_id):
    cita = get_object_or_404(Cita, id=cita_id)
    if request.method == "POST":
        form = DiagnosticoForm(request.POST, instance=cita)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Diagnóstico guardado correctamente.")
            return redirect("detalle_cita_doctor", cita_id=cita.id)
        else:
            messages.error(request, "❌ Error al guardar diagnóstico.")
    else:
        form = DiagnosticoForm(instance=cita)

    return render(request, "doctor/diagnostico.html", {
        "cita": cita,
        "paciente": cita.paciente,
        "form": form
    })


# ---------------------------
# Agregar o editar receta
# ---------------------------
@login_required
@user_passes_test(is_doctor)
def agregar_receta(request, cita_id):
    cita = get_object_or_404(Cita, id=cita_id)
    receta = getattr(cita, 'receta', None)
    
    # ✅ CORRECCIÓN: Obtener Signos Vitales de forma segura
    signos = getattr(cita, 'signosvitales', None) 

    if request.method == "POST":
        form = RecetaForm(request.POST, instance=receta)
        if form.is_valid():
            nueva_receta = form.save(commit=False)
            nueva_receta.cita = cita
            nueva_receta.doctor = request.user.doctor
            nueva_receta.save()
            messages.success(request, "✅ Receta guardada correctamente.")
            return redirect('detalle_cita_doctor', cita_id=cita.id)
        else:
            messages.error(request, "❌ Error al guardar la receta.")
    else:
        form = RecetaForm(instance=receta)

    return render(request, "doctor/agregar_receta.html", {
        "cita": cita,
        "paciente": cita.paciente,
        "form": form,
        "signos": signos  # ✅ AÑADIDO: Pasar la variable 'signos' al template
    })


# ---------------------------
# Generar PDF de receta
# ---------------------------
import os
from io import BytesIO
from django.urls import reverse 
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


@login_required
@user_passes_test(lambda u: hasattr(u, 'doctor'))
def generar_receta_pdf(request, cita_id):
    from reportlab.lib.enums import TA_CENTER

    cita = get_object_or_404(Cita, id=cita_id)
    receta = getattr(cita, 'receta', None)

    if not receta:
        messages.error(request, "❌ No hay receta para esta cita.")
        return redirect('detalle_cita_doctor', cita_id=cita.id)

    paciente = cita.paciente
    doctor = cita.doctor
    signos = getattr(cita, 'signosvitales', None)

    # --- ✅ Cambiar el estado de la cita a “Atendida” ---
    # Esto es crucial para marcar la cita como finalizada.
    cita.estado = "Atendida"
    cita.save()

    # --- Crear el PDF ---
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()

    azul_oscuro = colors.HexColor('#2E86C1')
    azul_claro = colors.HexColor('#AED6F1')
    azul_btn = colors.HexColor('#4A90E2')

    title_style = ParagraphStyle('TitleCustom', parent=styles['Title'], fontName='Helvetica-Bold', fontSize=22, textColor=azul_oscuro, alignment=TA_CENTER, spaceAfter=8)
    subtitle_style = ParagraphStyle('SubtitleCustom', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=14, textColor=azul_btn, spaceAfter=6)
    label_style = ParagraphStyle('LabelCustom', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=11, textColor=azul_oscuro)
    normal_style = ParagraphStyle('NormalCustom', parent=styles['Normal'], fontName='Helvetica', fontSize=11, textColor=colors.black)

    # --- Encabezado ---
    # Nota: La variable settings debe estar importada para que esto funcione.
    # Si no tienes settings.BASE_DIR disponible, usa la ruta estática directa.
    try:
        from django.conf import settings
        logo_path = os.path.join(settings.BASE_DIR, "static", "citas", "img", "logo.png")
    except ImportError:
        # En caso de que settings no esté importado o disponible
        logo_path = "" # Ajusta esto a tu necesidad si no usas settings

    header_title = Paragraph("HOSPITAL SAN PEDRO", title_style)
    header_subtitle = Paragraph("Av. 5 de Mayo Sur Nº 29, Zacapoaxtla, Pue. • Tel: 233 314-30-84", normal_style)

    header_cells = []
    if logo_path and os.path.exists(logo_path):
        header_cells = [[Image(logo_path, width=60, height=60), header_title], ["", header_subtitle]]
    else:
        # Si no se encuentra el logo, usa solo el título y subtítulo
        header_cells = [["", header_title], ["", header_subtitle]]

    header_table = Table(header_cells, colWidths=[70, 360])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (1,0), (1,-1), 'CENTER'),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 10))
    elements.append(Table([[" "]], colWidths=[430], rowHeights=[1], style=TableStyle([('BACKGROUND', (0,0), (-1,-1), azul_oscuro)])))
    elements.append(Spacer(1, 14))
    elements.append(Paragraph("Receta Médica", title_style))
    elements.append(Spacer(1, 10))

    # --- Datos del paciente ---
    fecha_str = cita.fecha.strftime('%d/%m/%Y') if cita.fecha else "---"
    hora_str = cita.hora.strftime('%H:%M') if cita.hora else "---"

    data_paciente = [
        [Paragraph("<b>Nombre:</b>", label_style), Paragraph(f"{paciente.nombre} {paciente.apellido}", normal_style)],
        [Paragraph("<b>Edad:</b>", label_style), Paragraph(f"{getattr(paciente, 'edad', '---')} años", normal_style)],
        [Paragraph("<b>Médico:</b>", label_style), Paragraph(f"Dr. {doctor.user.get_full_name()}", normal_style)],
        [Paragraph("<b>Fecha y hora:</b>", label_style), Paragraph(f"{fecha_str} {hora_str}", normal_style)],
    ]
    table_paciente = Table(data_paciente, colWidths=[120, 330])
    table_paciente.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,-1), azul_btn),
        ('TEXTCOLOR', (0,0), (0,-1), colors.white),
        ('BACKGROUND', (1,0), (1,-1), azul_claro),
        ('BOX', (0,0), (-1,-1), 1, azul_oscuro),
    ]))
    elements.append(Paragraph("Información del Paciente", subtitle_style))
    elements.append(table_paciente)
    elements.append(Spacer(1, 14))

    # --- Diagnóstico ---
    if cita.diagnostico:
        elements.append(Paragraph("Diagnóstico", subtitle_style))
        elements.append(Paragraph(cita.diagnostico, normal_style))
        elements.append(Spacer(1, 14))

    # --- Medicamentos e Indicaciones ---
    elements.append(Paragraph("Medicamentos", subtitle_style))
    elements.append(Paragraph((receta.medicamentos or "---").replace('\n', '<br/>'), normal_style))
    elements.append(Spacer(1, 8))
    elements.append(Paragraph("Indicaciones", subtitle_style))
    elements.append(Paragraph((receta.indicaciones or "---").replace('\n', '<br/>'), normal_style))
    elements.append(Spacer(1, 28))

    # --- Firma ---
    cedula = getattr(doctor, 'cedula_profesional', '') or '---'
    elements.append(Paragraph(f"Dr. {doctor.user.get_full_name()} — Cédula: {cedula}", normal_style))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph("______________________________", normal_style))
    elements.append(Paragraph("Firma del Doctor", normal_style))

    def draw_footer(canv, doc_obj):
        canv.saveState()
        canv.setStrokeColor(azul_oscuro)
        canv.setLineWidth(0.5)
        page_width, page_height = doc_obj.pagesize
        canv.line(40, 40, page_width - 40, 40)
        canv.setFont("Helvetica", 9)
        canv.setFillColor(colors.black)
        canv.drawString(40, 28, f"Dr. {doctor.user.get_full_name()}")
        canv.drawRightString(page_width - 40, 28, f"Página {canv.getPageNumber()}")
        canv.restoreState()

    doc.build(elements, onFirstPage=draw_footer, onLaterPages=draw_footer)
    pdf = buffer.getvalue()
    buffer.close()

    # ✅ CORRECCIÓN: Devolvemos el PDF como archivo adjunto.
    # El navegador lo descargará/abrirá en una nueva pestaña (según el JS).
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="receta_{paciente.nombre}.pdf"'
    
    return response


@login_required
def detalle_paciente(request, paciente_id):
    paciente = get_object_or_404(Paciente, id=paciente_id)
    return render(request, 'recepcion/detalle_paciente.html', {'paciente': paciente})


@login_required
def buscar_pacientes_doctor(request):
    query = request.GET.get('q', '').strip()

    if query:
        pacientes = Paciente.objects.filter(
            Q(nombre__icontains=query) |
            Q(apellido_paterno__icontains=query) |
            Q(apellido_materno__icontains=query) |
            Q(numero__icontains=query)
        ).order_by('nombre')
    else:
        # si no se busca nada, mostrar todos
        pacientes = Paciente.objects.all().order_by('nombre')

    return render(request, 'doctor/buscar_pacientes.html', {
        'pacientes': pacientes,
        'query': query,
    })

    #--------------------
# --- Reportes en PDF ---
# ---------------------------
import io
from django.http import FileResponse
from datetime import timedelta
from django.utils import timezone
# 📄 Función general para crear el PDF
def generar_pdf_reporte(titulo, citas):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer)
    styles = getSampleStyleSheet()

    story = [Paragraph(titulo, styles['Title']), Spacer(1, 12)]

    # Encabezados de tabla
    data = [["Paciente", "Doctor", "Fecha", "Estado"]]

    # Agregar datos de las citas
    for c in citas:
        try:
            # Nombre completo del paciente (según campos disponibles)
            nombre_paciente = ""
            if hasattr(c.paciente, "nombre") and hasattr(c.paciente, "apellido_paterno"):
                nombre_paciente = f"{c.paciente.nombre} {c.paciente.apellido_paterno} {getattr(c.paciente, 'apellido_materno', '')}".strip()
            elif hasattr(c.paciente, "nombre_completo"):
                nombre_paciente = c.paciente.nombre_completo
            elif hasattr(c.paciente, "nombre"):
                nombre_paciente = c.paciente.nombre
            else:
                nombre_paciente = "Paciente desconocido"

            nombre_doctor = c.doctor.user.get_full_name() if hasattr(c.doctor, 'user') else "Doctor no asignado"

            data.append([
                nombre_paciente,
                nombre_doctor,
                str(c.fecha),
                c.estado
            ])
        except Exception as e:
            print("Error al procesar cita:", e)

    story.append(Table(data))
    doc.build(story)
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename=f"{titulo}.pdf")


# 📆 Reporte Diario
def reporte_dia(request):
    fecha_str = request.GET.get('fecha')
    if fecha_str:
        fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
    else:
        fecha = date.today()

    citas = Cita.objects.filter(fecha=fecha)
    
    if 'descargar' in request.GET:
        return generar_pdf_reporte(f"Reporte Diario - {fecha}", citas)

    return render(request, 'dashboard_administradora.html', {
        'tab_activa': 'reportes',
        'citas_report': citas,
    })


# 📅 Reporte Semanal
def reporte_semana(request):
    fecha_str = request.GET.get('fecha')
    if fecha_str:
        fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
    else:
        fecha = date.today()

    # Calcula el rango de la semana (lunes a domingo)
    inicio_semana = fecha - timedelta(days=fecha.weekday())
    fin_semana = inicio_semana + timedelta(days=6)

    citas = Cita.objects.filter(fecha__range=(inicio_semana, fin_semana))

    if 'descargar' in request.GET:
        return generar_pdf_reporte(f"Reporte Semanal - Semana del {inicio_semana} al {fin_semana}", citas)

    return render(request, 'dashboard_administradora.html', {
        'tab_activa': 'reportes',
        'citas_report': citas,
    })


# 🗓️ Reporte Mensual
def reporte_mes(request):
    fecha_str = request.GET.get('fecha')
    if fecha_str:
        fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
    else:
        fecha = date.today()

    # Calcula inicio y fin del mes
    inicio_mes = fecha.replace(day=1)
    if fecha.month == 12:
        fin_mes = fecha.replace(year=fecha.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        fin_mes = fecha.replace(month=fecha.month + 1, day=1) - timedelta(days=1)

    citas = Cita.objects.filter(fecha__range=(inicio_mes, fin_mes))

    if 'descargar' in request.GET:
        return generar_pdf_reporte(f"Reporte Mensual - {fecha.strftime('%B %Y')}", citas)

    return render(request, 'dashboard_administradora.html', {
        'tab_activa': 'reportes',
        'citas_report': citas,
    })


def detalle_paciente(request, paciente_id):
    paciente = get_object_or_404(Paciente, id=paciente_id)
    return render(request, 'doctor/detalle_paciente.html', {'paciente': paciente})


@login_required
@user_passes_test(lambda u: hasattr(u, 'doctor'))
def imprimir_historial_paciente(request, paciente_id):
    from io import BytesIO
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, Image
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    import os

    paciente = get_object_or_404(Paciente, id=paciente_id)
    doctor = getattr(request.user, 'doctor', None)
    citas = Cita.objects.filter(paciente=paciente, doctor=doctor).order_by('-fecha')

    if not citas.exists():
        messages.warning(request, "No hay citas registradas para este paciente.")
        return redirect('dashboard_doctor')

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()

    azul_oscuro = colors.HexColor('#2E86C1')
    azul_claro = colors.HexColor('#AED6F1')
    azul_btn = colors.HexColor('#4A90E2')

    title_style = ParagraphStyle('TitleCustom', parent=styles['Title'], fontName='Helvetica-Bold', fontSize=22, textColor=azul_oscuro, alignment=TA_CENTER)
    subtitle_style = ParagraphStyle('SubtitleCustom', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=14, textColor=azul_btn, spaceAfter=6)
    label_style = ParagraphStyle('LabelCustom', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=11, textColor=azul_oscuro)
    normal_style = ParagraphStyle('NormalCustom', parent=styles['Normal'], fontName='Helvetica', fontSize=11, textColor=colors.black)

    # --- Encabezado ---
    logo_path = os.path.join(settings.BASE_DIR, "static", "citas", "img", "logo.png")
    header_title = Paragraph("HOSPITAL SAN PEDRO", title_style)
    header_subtitle = Paragraph("Av. 5 de Mayo Sur Nº 29, Zacapoaxtla, Pue. • Tel: 233 314-30-84", normal_style)

    header_cells = []
    if os.path.exists(logo_path):
        header_cells = [[Image(logo_path, width=60, height=60), header_title], ["", header_subtitle]]
    else:
        header_cells = [["", header_title], ["", header_subtitle]]

    header_table = Table(header_cells, colWidths=[70, 360])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (1,0), (1,-1), 'CENTER'),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 10))
    elements.append(Table([[" "]], colWidths=[430], rowHeights=[1], style=TableStyle([('BACKGROUND', (0,0), (-1,-1), azul_oscuro)])))
    elements.append(Spacer(1, 14))
    elements.append(Paragraph("Historial Clínico del Paciente", title_style))
    elements.append(Spacer(1, 14))

    # --- Información del Paciente ---
    data_paciente = [
        [Paragraph("<b>Nombre:</b>", label_style), Paragraph(f"{paciente.nombre} {paciente.apellido}", normal_style)],
        [Paragraph("<b>Edad:</b>", label_style), Paragraph(f"{getattr(paciente, 'edad', '---')} años", normal_style)],
        [Paragraph("<b>Doctor:</b>", label_style), Paragraph(f"Dr. {doctor.user.get_full_name()}", normal_style)],
    ]
    table_paciente = Table(data_paciente, colWidths=[120, 330])
    table_paciente.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,-1), azul_btn),
        ('TEXTCOLOR', (0,0), (0,-1), colors.white),
        ('BACKGROUND', (1,0), (1,-1), azul_claro),
        ('BOX', (0,0), (-1,-1), 1, azul_oscuro),
    ]))
    elements.append(Paragraph("Información del Paciente", subtitle_style))
    elements.append(table_paciente)
    elements.append(Spacer(1, 18))

    # --- Detalle de cada cita ---
    for c in citas:
        fecha_str = c.fecha.strftime('%d/%m/%Y') if c.fecha else "---"
        elements.append(Paragraph(f"📅 Cita del {fecha_str}", subtitle_style))
        elements.append(Paragraph(f"<b>Estado:</b> {c.estado}", normal_style))

        # Diagnóstico
        diag = c.nuevo_diagnostico or c.diagnostico or "---"
        elements.append(Paragraph("<b>Diagnóstico:</b>", label_style))
        elements.append(Paragraph(diag, normal_style))
        elements.append(Spacer(1, 6))

        # Medicamentos
        if hasattr(c, 'receta') and c.receta.medicamentos:
            elements.append(Paragraph("<b>Medicamentos:</b>", label_style))
            elements.append(Paragraph(c.receta.medicamentos.replace('\n', '<br/>'), normal_style))
        else:
            elements.append(Paragraph("<b>Medicamentos:</b> ---", normal_style))
        elements.append(Spacer(1, 6))

        # Indicaciones
        if hasattr(c, 'receta') and c.receta.indicaciones:
            elements.append(Paragraph("<b>Indicaciones:</b>", label_style))
            elements.append(Paragraph(c.receta.indicaciones.replace('\n', '<br/>'), normal_style))
        else:
            elements.append(Paragraph("<b>Indicaciones:</b> ---", normal_style))
        elements.append(Spacer(1, 16))

    # --- Firma ---
    cedula = getattr(doctor, 'cedula_profesional', '') or '---'
    elements.append(Spacer(1, 20))
    elements.append(Paragraph(f"Dr. {doctor.user.get_full_name()} — Cédula: {cedula}", normal_style))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph("______________________________", normal_style))
    elements.append(Paragraph("Firma del Doctor", normal_style))

    def draw_footer(canv, doc_obj):
        canv.saveState()
        canv.setStrokeColor(azul_oscuro)
        canv.setLineWidth(0.5)
        page_width, page_height = doc.pagesize
        canv.line(40, 40, page_width - 40, 40)
        canv.setFont("Helvetica", 9)
        canv.setFillColor(colors.black)
        canv.drawString(40, 28, f"Dr. {doctor.user.get_full_name()}")
        canv.drawRightString(page_width - 40, 28, f"Página {canv.getPageNumber()}")
        canv.restoreState()

    doc.build(elements, onFirstPage=draw_footer, onLaterPages=draw_footer)
    pdf = buffer.getvalue()
    buffer.close()

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="historial_{paciente.nombre}.pdf"'
    return response

# ---------------------------
# --- API REST con DRF ---
# ---------------------------
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.authtoken.models import Token   
from .serializers import RegisterSerializer, CitaSerializer, SignosVitalesSerializer
from django.contrib.auth import get_user_model
CustomUser = get_user_model()
from django.db import IntegrityError # <-- ¡Importa esto!
from django.contrib.auth import authenticate      # Para verificar usuario y contraseña


class RegisterAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        data = request.data

        username = data.get('username')
        password = data.get('password')
        nombre = data.get('nombre')
        apellido_paterno = data.get('apellido_paterno')
        apellido_materno = data.get('apellido_materno')
        email = data.get('email')  
        role = data.get('role', 'enfermera') 

        # 1. Validar campos obligatorios
        if not all([username, password, nombre, apellido_paterno, email]):
            return Response({'error': 'Faltan campos obligatorios.'}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Verificar si el usuario ya existe (Verificación de Django)
        if CustomUser.objects.filter(username=username).exists():
            # Devuelve 400 antes de intentar tocar la base de datos
            return Response({'error': 'El nombre de usuario ya existe.'}, status=status.HTTP_400_BAD_REQUEST)

        # 3. Crear usuario con manejo de errores de base de datos
        try:
            user = CustomUser.objects.create_user(
                username=username,
                password=password,
                email=email,
                nombre=nombre,
                apellido_paterno=apellido_paterno,
                apellido_materno=apellido_materno or '',
                role=role
            )
            return Response({'mensaje': 'Usuario creado correctamente. Inicia sesión.'}, status=status.HTTP_201_CREATED)

        except IntegrityError:
            # Captura el error de PostgreSQL (UniqueViolation) si la verificación anterior falla
            # o si el email también es único y está duplicado.
            return Response({'error': 'El nombre de usuario o correo electrónico ya están registrados.'}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            # Captura cualquier otro error de servidor no esperado.
            return Response({'error': f'Error interno del servidor: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class LoginAPIView(APIView):
    permission_classes = [permissions.AllowAny]
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        user = authenticate(username=username, password=password)

        if user and hasattr(user, 'role') and user.role == 'enfermera':
            # Ahora, 'Token' tendrá el atributo 'objects'
            token, _ = Token.objects.get_or_create(user=user)
            return Response({'token': token.key, 'username': user.username})

        return Response({'detail':'Credenciales inválidas o no eres enfermera'}, status=status.HTTP_401_UNAUTHORIZED)
    
from datetime import datetime, timedelta

class CitasListAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # CAMBIO: Usar __iexact para ignorar mayúsculas/minúsculas.
        citas = Cita.objects.all().select_related('paciente').order_by('fecha', 'hora') 
        # 1. Consulta base
        citas = Cita.objects.all().select_related('paciente').order_by('fecha', 'hora')

        # 2. Obtener el parámetro 'date' de la URL (Ej: '2025-10-17')
        target_date_str = request.query_params.get('date') 

        if target_date_str:
            try:
                # 3. FILTRADO CORREGIDO: Usamos el campo 'fecha' que sí existe.
                
                # Si 'fecha' es un DateField, Django puede filtrar por el string directo.
                # Utilizamos 'fecha__exact' o simplemente 'fecha'
                citas = citas.filter(fecha=target_date_str)
                
                # NOTA: La línea original de ordenación ya usa 'fecha' y 'hora', 
                # lo que confirma que son campos separados.
                
            except Exception:
                # Manejar cualquier error de conversión de fecha si fuera necesario, 
                # aunque 'fecha=target_date_str' debería ser robusto si el formato es 'YYYY-MM-DD'.
                pass 
                
        # 4. Serializar y devolver los datos
        ser = CitaSerializer(citas, many=True)
        return Response(ser.data)
    
class SignosVitalesCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request):
        # Si ya existe signos para la cita queremos actualizar, sino crear.
        data = request.data.copy()
        cita_id = data.get('cita')
        if not cita_id:
            return Response({'detail':'Se requiere cita'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            cita = Cita.objects.get(id=cita_id)
        except Cita.DoesNotExist:
            return Response({'detail':'Cita no encontrada'}, status=status.HTTP_404_NOT_FOUND)

        # buscar existente
        signos = getattr(cita, 'signosvitales', None)
        if signos:
            ser = SignosVitalesSerializer(signos, data=data, partial=True)
        else:
            ser = SignosVitalesSerializer(data=data)

        if ser.is_valid():
            sv = ser.save()
            # opcional: marcar cita como 'atendida'
            cita.estado = 'atendida'
            cita.save()
            return Response(SignosVitalesSerializer(sv).data, status=status.HTTP_201_CREATED)
        return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
    
    
    # views.py (Ejemplo de la vista de detalle de cita)

class CitaDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        try:
            # ✅ OPTIMIZACIÓN: Usar select_related para ambas relaciones OneToOne (directa e inversa).
            cita = (Cita.objects.filter(pk=pk)
                       .select_related('paciente', 'signosvitales') # <- Carga paciente y signos vitales
                       .first())

            if not cita:
                return Response({"detail": "Cita no encontrada"}, status=status.HTTP_404_NOT_FOUND)

            # El serializador ahora utiliza get_signosvitales() para incluir el objeto
            ser = CitaSerializer(cita)
            return Response(ser.data)

        except Exception as e:
            return Response({"detail": "Error interno del servidor: " + str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        from django.db.models import F
