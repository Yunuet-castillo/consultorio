
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
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from datetime import datetime, date, timedelta
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
import pytesseract
from PIL import Image as PILImage          # ✔ CORRECTO
from reportlab.platypus import Image as PDFImage   # ✔ NO interfiere
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def leer_pdf(ruta):
    texto = ""
    with open(ruta, 'rb') as f:
        reader = PdfReader(f)
        for page in reader.pages:
            texto += page.extract_text() or ""
    return texto.strip()

def leer_imagen(ruta):
    imagen = PILImage.open(ruta)   # ✔ YA FUNCIONA
    texto = pytesseract.image_to_string(imagen, lang='spa')
    return texto.strip()

def agregar_estudio(request, paciente_id):
    paciente = get_object_or_404(Paciente, id=paciente_id)
    cita = Cita.objects.filter(paciente=paciente).order_by('-fecha').first()

    if request.method == 'POST':
        form = EstudioForm(request.POST, request.FILES)
        if form.is_valid():
            estudio = form.save(commit=False)
            estudio.paciente = paciente
            estudio.save()

            ruta = estudio.archivo.path
            extension = os.path.splitext(ruta)[1].lower()

            if extension == '.pdf':
                texto_extraido = leer_pdf(ruta)
            elif extension in ['.jpg', '.jpeg', '.png']:
                texto_extraido = leer_imagen(ruta)
            else:
                texto_extraido = "Tipo de archivo no compatible."

            estudio.texto_extraido = texto_extraido
            estudio.save()

            messages.success(request, "✅ Estudio agregado correctamente.")
            # Limpiar el formulario después de guardar
            form = EstudioForm()
        else:
            messages.error(request, "❌ No se pudo agregar el estudio. Revisa los campos.")
    else:
        form = EstudioForm()

    return render(request, 'doctor/agregar_estudio.html', {
        'form': form,
        'paciente': paciente,
        'cita': cita
    })


# 🔧 Ruta típica de instalación (ajústala si es diferente)

from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Spacer, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from .models import Cita, Estudio, SignosVitales


# -----------------------------------------------------------
# PIE DE PÁGINA
# -----------------------------------------------------------
def pie_pagina(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 9)
    canvas.drawString(40, 25, "Hospital San Pedro — Historial Clínico")
    canvas.drawRightString(570, 25, f"Página {doc.page}")
    canvas.restoreState()


# -----------------------------------------------------------
# HISTORIAL CON DISEÑO + VIÑETAS + CAMPOS CORRECTOS
# -----------------------------------------------------------
def imprimir_historial(request, cita_id):
    cita = get_object_or_404(Cita, id=cita_id)
    paciente = cita.paciente

    signos = SignosVitales.objects.filter(cita__paciente=paciente).order_by('-cita__fecha')
    estudios = Estudio.objects.filter(paciente=paciente).order_by('-fecha_subida')

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="historial_{paciente.nombre}_{cita.fecha.strftime("%Y%m%d")}.pdf"'

    pdf = SimpleDocTemplate(
        response,
        pagesize=letter,
        leftMargin=30,
        rightMargin=30,
        topMargin=60,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()
    
    azul_oscuro = colors.HexColor("#1a365d")
    azul_medio = colors.HexColor("#2d5a8c")
    azul_claro = colors.HexColor("#e6f2ff")
    gris_medio = colors.HexColor("#4a5568")

    title_style = ParagraphStyle(
        "title",
        fontSize=22,
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
        textColor=azul_oscuro,
        spaceAfter=20,
        spaceBefore=10
    )

    section_title = ParagraphStyle(
        "section_title",
        fontSize=14,
        fontName="Helvetica-Bold",
        textColor=azul_medio,
        spaceBefore=20,
        spaceAfter=12,
        leftIndent=10
    )

    normal_style = ParagraphStyle(
        "normal",
        fontSize=10,
        fontName="Helvetica",
        textColor=gris_medio,
        leading=12
    )

    label_style = ParagraphStyle(
        "label",
        fontSize=10,
        fontName="Helvetica-Bold",
        textColor=azul_oscuro,
        spaceAfter=2
    )

    story = []

    # ------------------ ENCABEZADO ------------------
    try:
        logo = Image("static/citas/img/logo.png", width=60, height=60)
        header_data = [[logo, Paragraph("<b>HOSPITAL SAN PEDRO</b>", title_style)]]
        header_table = Table(header_data, colWidths=[70, 460])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ]))
        story.append(header_table)
    except:
        story.append(Paragraph("<b>HOSPITAL SAN PEDRO</b>", title_style))

    story.append(Spacer(1, 15))
    story.append(Paragraph("HISTORIAL CLÍNICO", title_style))
    story.append(Spacer(1, 15))

    # ------------------ SIGNOS VITALES ------------------
    story.append(Paragraph("• SIGNOS VITALES", section_title))

    if signos.exists():
        data = [[
            Paragraph("<b>Fecha</b>", label_style),
            Paragraph("<b>Peso</b>", label_style),
            Paragraph("<b>Presión</b>", label_style),
            Paragraph("<b>Temp.</b>", label_style),
            Paragraph("<b>F.C.</b>", label_style),
            Paragraph("<b>F.R.</b>", label_style),
            Paragraph("<b>Oxígeno</b>", label_style)
        ]]

        # ⛔ SOLUCIÓN AL ERROR: convertir TODO a texto
        for s in signos[:10]:
            data.append([
                Paragraph(str(s.cita.fecha.strftime("%d/%m/%Y")), normal_style),
                Paragraph(str(s.peso) + " kg" if s.peso is not None else "—", normal_style),
                Paragraph(str(s.presion_arterial) if s.presion_arterial else "—", normal_style),
                Paragraph(str(s.temperatura) + " °C" if s.temperatura is not None else "—", normal_style),
                Paragraph(str(s.frecuencia_cardiaca) if s.frecuencia_cardiaca is not None else "—", normal_style),
                Paragraph(str(s.frecuencia_respiratoria) if s.frecuencia_respiratoria is not None else "—", normal_style),
                Paragraph(str(s.saturacion_oxigeno) + "%" if s.saturacion_oxigeno is not None else "—", normal_style),
            ])

        table = Table(data, colWidths=[60, 50, 60, 50, 50, 50, 50])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), azul_claro),
            ('BOX', (0, 0), (-1, -1), 1, azul_medio),
            ('GRID', (0, 0), (-1, -1), 1, azul_claro),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        story.append(table)
    else:
        story.append(Paragraph("No se encontraron registros de signos vitales.", normal_style))

    story.append(Spacer(1, 20))

    # ------------------ DIAGNÓSTICOS ------------------
    story.append(Paragraph("• DIAGNÓSTICOS Y TRATAMIENTOS", section_title))

    citas_paciente = Cita.objects.filter(paciente=paciente).order_by('-fecha')[:5]

    for c in citas_paciente:
        diag = c.nuevo_diagnostico or c.diagnostico or "No registrado"
        medicamentos = c.medicamentos or "No registrado"
        indicaciones = c.instrucciones or "No registrado"

        cita_data = [
            [Paragraph(f"<b>CITA - {c.fecha.strftime('%d/%m/%Y')}</b>", label_style)],
            [Paragraph(f"<b>Diagnóstico:</b> {diag}", normal_style)],
            [Paragraph(f"<b>Medicamentos:</b> {medicamentos}", normal_style)],
            [Paragraph(f"<b>Indicaciones:</b> {indicaciones}", normal_style)],
        ]

        cita_table = Table(cita_data, colWidths=[500])
        cita_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), azul_claro),
            ('BOX', (0, 0), (-1, -1), 1, azul_medio),
            ('PADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(cita_table)
        story.append(Spacer(1, 12))

    # ------------------ ESTUDIOS ------------------
    story.append(Paragraph("• ESTUDIOS Y ANÁLISIS", section_title))

    for e in estudios[:3]:
        fecha_est = e.fecha_subida.strftime('%d/%m/%Y %H:%M')

        estudio_data = [
            [Paragraph(f"<b>ESTUDIO - {fecha_est}</b>", label_style)],
            [Paragraph(f"<b>Descripción:</b> {e.descripcion or 'Sin descripción'}", normal_style)],
            [Paragraph(f"<b>Texto extraído:</b> {e.texto_extraido or '(Sin texto leído)'}", normal_style)],
        ]

        estudio_table = Table(estudio_data, colWidths=[500])
        estudio_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), azul_claro),
            ('BOX', (0, 0), (-1, -1), 1, azul_medio),
            ('PADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(estudio_table)

        if e.archivo:
            ruta = e.archivo.path
            ext = os.path.splitext(ruta)[1].lower()
            if ext in ['.jpg', '.jpeg', '.png']:
                try:
                    story.append(Image(ruta, width=300, height=200))
                except:
                    story.append(Paragraph("(No se pudo cargar la imagen)", normal_style))

        story.append(Spacer(1, 20))

    # ------------------ FOOTER ------------------
    def pie_pagina(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.drawString(30, 25, "Hospital San Pedro - Historial Clínico Confidencial")
        canvas.drawRightString(580, 25, f"Página {canvas.getPageNumber()}")
        canvas.restoreState()

    pdf.build(story, onFirstPage=pie_pagina, onLaterPages=pie_pagina)

    messages.success(request, "✅ Historial clínico descargado con éxito.")
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
            request.session['paciente_id'] = paciente.id
            return redirect('agendar_cita')
        else:
            messages.error(request, "Error al registrar al paciente. Revisa los campos marcados.")
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

    # Obtener la cita con el paciente
    cita = get_object_or_404(
        Cita.objects.select_related('paciente'),
        id=cita_id
    )

    # Si envían un POST para guardar diagnóstico
    if request.method == "POST":
        nuevo = request.POST.get("diagnostico")


        if nuevo and nuevo.strip() != "":
            # Mover el diagnóstico actual como anterior
            if cita.diagnostico:
                cita.diagnostico_anterior = cita.diagnostico

            # Guardar el nuevo diagnóstico
            cita.diagnostico = nuevo
            cita.save()

            messages.success(request, "Diagnóstico actualizado correctamente.")
            return redirect("detalle_cita_doctor", cita_id=cita.id)

    # Obtener signos vitales y receta
    signos = getattr(cita, "signosvitales", None)
    receta = getattr(cita, "receta", None)

    # Traer diagnóstico de la cita anterior del mismo paciente
    diagnostico_anterior = (
        Cita.objects.filter(paciente=cita.paciente)
        .exclude(id=cita.id)
        .order_by("-fecha", "-hora")
        .first()
    )

    contexto = {
        "cita": cita,
        "paciente": cita.paciente,
        "signos": signos,
        "receta": receta,
        "diagnostico_anterior": diagnostico_anterior,
    }

    return render(request, "doctor/detalle_cita.html", contexto)






# ---------------------------
# Realizar o editar diagnóstico
# ---------------------------
from .models import DiagnosticoHistorico
@login_required
@user_passes_test(is_doctor)
def realizar_diagnostico(request, cita_id):
    cita = get_object_or_404(Cita, id=cita_id)

    if request.method == "POST":
        # obtén el texto directamente del POST (asegúrate que en la plantilla el textarea tiene name="diagnostico")
        texto = request.POST.get('diagnostico', '').strip()

        if texto:  # solo guardamos si hay texto
            # Guardar historial
            DiagnosticoHistorico.objects.create(
                cita=cita,
                texto=texto,
                doctor=request.user
            )

            # Guardar diagnóstico actual en la Cita
            cita.diagnostico = texto
            cita.save()

            messages.success(request, "✅ Diagnóstico guardado correctamente.")
            return redirect("detalle_cita_doctor", cita_id=cita.id)
        else:
            messages.error(request, "Por favor escribe el diagnóstico antes de guardar.")
    else:
        # GET
        pass

    # Si quieres mostrar un formulario ya existente para la interfaz, puedes seguir usando el form para renderizado
    form = DiagnosticoForm(instance=cita)
    historial = DiagnosticoHistorico.objects.filter(cita=cita).order_by('-fecha')

    return render(request, "doctor/diagnostico.html", {
        "cita": cita,
        "form": form,
        "historial": historial,
    })



    




# ---------------------------
# Agregar o editar receta
# ---------------------------
from reportlab.platypus import Image

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
from reportlab.lib.pagesizes import landscape, letter

@login_required
@user_passes_test(lambda u: hasattr(u, 'doctor'))
def generar_receta_pdf(request, cita_id):
    import os
    from io import BytesIO
    from django.shortcuts import get_object_or_404, redirect
    from django.http import HttpResponse
    from django.contrib import messages
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    from reportlab.lib import colors

    cita = get_object_or_404(Cita, id=cita_id)
    receta = getattr(cita, 'receta', None)

    if not receta:
        messages.error(request, "❌ No hay receta para esta cita.")
        return redirect('detalle_cita_doctor', cita_id=cita.id)

    paciente = cita.paciente
    doctor = cita.doctor

    # Marcar cita como atendida
    cita.estado = "Atendida"
    cita.save()

    # Configurar página horizontal
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        leftMargin=25,
        rightMargin=25,
        topMargin=20,
        bottomMargin=25
    )

    elements = []
    styles = getSampleStyleSheet()

    # Paleta de colores
    azul_oscuro = colors.HexColor("#1a365d")
    azul_medio = colors.HexColor("#2d5a8c")
    azul_claro = colors.HexColor("#e6f2ff")
    gris_medio = colors.HexColor("#4a5568")

    # DATOS DEFINIDOS DIRECTAMENTE
    CEDULA_PROFESIONAL = "8025534"
    ESPECIALIDAD = "GINECOLOGÍA, OBSTETRICIA, MEDICINA MATERNO-FETAL"
    HOSPITAL_NOMBRE = "Hospital San Pedro"

    # Estilos personalizados
    titulo_estilo = ParagraphStyle('Titulo', fontName="Helvetica-Bold", fontSize=18, alignment=TA_CENTER, textColor=azul_oscuro, spaceAfter=10, spaceBefore=0)
    subtitulo_estilo = ParagraphStyle('Subtitulo', fontName="Helvetica-Bold", fontSize=11, textColor=azul_medio, spaceAfter=6, spaceBefore=8)
    label_estilo = ParagraphStyle('Label', fontName="Helvetica-Bold", fontSize=9, textColor=azul_oscuro, spaceAfter=1)
    normal_estilo = ParagraphStyle('Normal', fontName="Helvetica", fontSize=9, textColor=gris_medio, leading=11)
    firma_estilo = ParagraphStyle('Firma', fontName="Helvetica-Bold", fontSize=10, textColor=azul_oscuro, alignment=TA_CENTER, spaceBefore=25)  # Aumentado de 15 a 25

         # ------------------ ENCABEZADO SUPER COMPACTO ------------------
    from django.conf import settings
    logo_path = os.path.join(settings.BASE_DIR, "static", "citas", "img", "logo.png")
    
    # Encabezado en una sola línea
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=80, height=80)  # Logo más pequeño
        encabezado_cells = [logo, Paragraph(f"<b>{HOSPITAL_NOMBRE}</b> - Receta Médica", titulo_estilo)]
    else:
        encabezado_cells = [Paragraph(f"<b>{HOSPITAL_NOMBRE}</b> - Receta Médica", titulo_estilo), ""]

    header_table = Table([encabezado_cells], colWidths=[50, 660])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
    ]))
    elements.append(header_table)

    # Información de contacto compacta - MEJOR VISUALIZACIÓN
    contacto_text = f"""
    <b>Av. 5 de Mayo Sur Nº 29</b><br/>
    Zacapoaxtla, Pue.<br/>
    Tel: 233 314 3084<br/>
    Cita: {cita.fecha.strftime('%d/%m/%Y')}
    """
    contacto_style = ParagraphStyle('Contacto', fontName="Helvetica", fontSize=8, textColor=gris_medio, alignment=TA_RIGHT, leading=10)
    
    # Tabla para información de contacto alineada a la derecha
    contacto_table = Table([[Paragraph(contacto_text, contacto_style)]], colWidths=[710])
    contacto_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(contacto_table)

    # Línea decorativa
    elements.append(Spacer(1, 5))
    elements.append(Table([[""]], colWidths=[710], rowHeights=[1], style=TableStyle([('BACKGROUND', (0,0), (-1,-1), azul_medio)])))
    elements.append(Spacer(1, 8))

    # ------------------ INFORMACIÓN DEL PACIENTE Y MÉDICO ------------------
    paciente_nombre = f"{paciente.nombre} {paciente.apellido_paterno} {paciente.apellido_materno or ''}"
    
    # Convertir fecha de nacimiento a string
    fecha_nac = getattr(paciente, 'fecha_nacimiento', None)
    fecha_nac_str = fecha_nac.strftime('%d/%m/%Y') if fecha_nac else '---'

    info_data = [
        [
            Paragraph("<b>INFORMACIÓN DEL PACIENTE</b>", subtitulo_estilo),
            Paragraph("<b>DATOS MÉDICOS</b>", subtitulo_estilo)
        ],
        [
            Table([
                [Paragraph("Nombre:", label_estilo), Paragraph(paciente_nombre, normal_estilo)],
                [Paragraph("Edad:", label_estilo), Paragraph(f"{getattr(paciente, 'edad', '---')} años", normal_estilo)],
                [Paragraph("Fecha nac.:", label_estilo), Paragraph(fecha_nac_str, normal_estilo)],
            ], colWidths=[80, 200]),

            Table([
                [Paragraph("Médico:", label_estilo), Paragraph(f"Dr. {doctor.user.get_full_name()}", normal_estilo)],
                [Paragraph("Especialidad:", label_estilo), Paragraph(ESPECIALIDAD, normal_estilo)],
                [Paragraph("Cédula:", label_estilo), Paragraph(CEDULA_PROFESIONAL, normal_estilo)],
            ], colWidths=[80, 200])
        ]
    ]

    info_table = Table(info_data, colWidths=[365, 365])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), azul_claro),
        ('BOX', (0, 0), (-1, -1), 1, azul_medio),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 10))

    # ------------------ SIGNOS VITALES ------------------
    # Obtener signos vitales de la base de datos
    signos_vitales_data = [
        [
            Paragraph("<b>SIGNOS VITALES</b>", subtitulo_estilo),
            Paragraph("<b>SIGNOS VITALES</b>", subtitulo_estilo)
        ],
        [
            Table([
                [Paragraph("Temperatura:", label_estilo), Paragraph(f"{getattr(cita, 'temperatura', '---')} °C", normal_estilo)],
                [Paragraph("Presión:", label_estilo), Paragraph(f"{getattr(cita, 'presion_arterial', '---')} mmHg", normal_estilo)],
                [Paragraph("F. Cardíaca:", label_estilo), Paragraph(f"{getattr(cita, 'frecuencia_cardiaca', '---')} lpm", normal_estilo)],
            ], colWidths=[80, 120]),
            
            Table([
                [Paragraph("F. Respiratoria:", label_estilo), Paragraph(f"{getattr(cita, 'frecuencia_respiratoria', '---')} rpm", normal_estilo)],
                [Paragraph("Sat. O2:", label_estilo), Paragraph(f"{getattr(cita, 'saturacion_oxigeno', '---')}%", normal_estilo)],
                [Paragraph("Peso:", label_estilo), Paragraph(f"{getattr(cita, 'peso', '---')} kg", normal_estilo)],
            ], colWidths=[80, 120])
        ]
    ]

    signos_vitales_table = Table(signos_vitales_data, colWidths=[365, 365])
    signos_vitales_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), azul_claro),
        ('BOX', (0, 0), (-1, -1), 1, azul_medio),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
    ]))
    elements.append(signos_vitales_table)
    elements.append(Spacer(1, 10))

    # ------------------ DIAGNÓSTICO ------------------
    if cita.diagnostico:
        diag_table = Table([
            [Paragraph("DIAGNÓSTICO", subtitulo_estilo)],
            [Paragraph(cita.diagnostico.replace("\n", "<br/>"), normal_estilo)]
        ], colWidths=[730])
        diag_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), azul_claro),
            ('BOX', (0, 0), (-1, -1), 1, azul_medio),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(diag_table)
        elements.append(Spacer(1, 10))

    # ------------------ MEDICAMENTOS E INDICACIONES ------------------
        # ------------------ MEDICAMENTOS E INDICACIONES ------------------
    contenido_data = [
        [Paragraph("<b>MEDICAMENTOS PRESCRITOS</b>", subtitulo_estilo), Paragraph("<b>INDICACIONES MÉDICAS</b>", subtitulo_estilo)]
    ]
    
    medicamentos_texto = receta.medicamentos.replace("\n", "<br/>") if receta.medicamentos else "No se prescribieron medicamentos"
    indicaciones_texto = receta.indicaciones.replace("\n", "<br/>") if receta.indicaciones else "No hay indicaciones específicas"
    
    contenido_data.append([Paragraph(medicamentos_texto, normal_estilo), Paragraph(indicaciones_texto, normal_estilo)])

    contenido_table = Table(contenido_data, colWidths=[365, 365])
    contenido_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), azul_claro),
        ('BOX', (0, 0), (-1, -1), 1, azul_medio),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
    ]))
    elements.append(contenido_table)
    elements.append(Spacer(1, 35))

    # ------------------ FIRMA ------------------
    firma_data = [
        [Paragraph("______________________________", firma_estilo)],
        [Paragraph(f"Dr. {doctor.user.get_full_name()}", firma_estilo)],
        [Paragraph(f"Cédula Profesional: {CEDULA_PROFESIONAL}", normal_estilo)],
    ]
    firma_table = Table(firma_data, colWidths=[200])
    firma_table.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))
    contenedor_firma = Table([[firma_table]], colWidths=[730])
    contenedor_firma.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'RIGHT')]))
    elements.append(contenedor_firma)

    # ------------------ FOOTER ------------------
    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(gris_medio)
        canvas.setStrokeColor(azul_claro)
        # Línea en posición correcta
        canvas.line(25, 25, 767, 25)
        # Texto en posiciones correctas
        canvas.drawString(25, 15, f"{HOSPITAL_NOMBRE} - Receta Médica Oficial")
        canvas.drawCentredString(396, 15, "Documento confidencial - Uso médico exclusivo")
        canvas.drawRightString(767, 15, f"Página {canvas.getPageNumber()}")
        canvas.restoreState()

    # Construir el PDF
    doc.build(elements, onFirstPage=footer, onLaterPages=footer)

    pdf = buffer.getvalue()
    buffer.close()

    response = HttpResponse(pdf, content_type="application/pdf")
    response['Content-Disposition'] = f'attachment; filename="receta_medica_{paciente.nombre}_{cita.fecha.strftime("%Y%m%d")}.pdf"'

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
            Q(numero__icontains=query) |
            Q(telefono__icontains=query)        # ← ✔️ Busca por teléfono
        ).order_by('nombre')
    else:
        pacientes = Paciente.objects.all().order_by('nombre')

    # 🔥 Agregar la última cita de cada paciente
    pacientes_con_cita = []
    for p in pacientes:
        ultima_cita = Cita.objects.filter(paciente=p).order_by('-fecha', '-hora').first()
        pacientes_con_cita.append({
            'paciente': p,
            'ultima_cita': ultima_cita
        })

    return render(request, 'doctor/buscar_pacientes.html', {
        'pacientes_con_cita': pacientes_con_cita,
        'query': query,
    })


    #--------------------
# --- Reportes en PDF ---
# ---------------------------
def reporte_dia(request):
    print("Entró a reporte_dia")  # Se verá en consola
    return render(request, "reportes/reporte_dia.html")

def reporte_semana(request):
    print("Entró a reporte_semana")  # Se verá en consola
    return render(request, "reportes/reporte_semana.html")

def reporte_mes(request):
    print("Entró a reporte_mes")  # Se verá en consola
    return render(request, "reportes/reporte_mes.html")


# ---------------------------
# --- Reportes en PDF ---
# ---------------------------

import io
from django.http import FileResponse, HttpResponse
from datetime import datetime, date, timedelta
from django.utils import timezone
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import Cita

# ✅ FUNCIÓN CORREGIDA - usa el campo role en lugar de grupos
def is_administradora(user):
    return user.is_authenticated and user.role.lower() == 'administradora'

# 📄 Función general para crear el PDF
def generar_pdf_reporte(titulo, citas):
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()

    # Estilos
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=30,
        textColor=colors.HexColor("#1a365d"),
        alignment=1
    )
    
    story = []
    
    # Título
    story.append(Paragraph(titulo, title_style))
    story.append(Spacer(1, 20))
    
    if citas.exists():
        # Encabezados de tabla
        data = [["Paciente", "Doctor", "Fecha", "Hora", "Estado"]]
        
        for cita in citas:
            paciente_nombre = f"{cita.paciente.nombre} {cita.paciente.apellido_paterno} {cita.paciente.apellido_materno or ''}"
            doctor_nombre = cita.doctor.user.get_full_name() if cita.doctor else "No asignado"
            
            data.append([
                paciente_nombre,
                doctor_nombre,
                cita.fecha.strftime('%d/%m/%Y'),
                cita.hora.strftime('%H:%M') if hasattr(cita.hora, 'strftime') else str(cita.hora),
                cita.estado
            ])
        
        # Crear tabla
        table = Table(data, colWidths=[180, 150, 80, 60, 80])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2d5a8c")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#f8f9fa")),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#dee2e6"))
        ]))
        story.append(table)
    else:
        # Mensaje cuando no hay citas
        no_data_style = ParagraphStyle(
            'NoData',
            parent=styles['BodyText'],
            fontSize=12,
            textColor=colors.gray,
            alignment=1
        )
        story.append(Paragraph("No hay citas para el período seleccionado.", no_data_style))
    
    doc.build(story)
    buffer.seek(0)
    
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{titulo.replace(" ", "_")}.pdf"'
    return response

# 📆 Reporte Diario
@login_required
@user_passes_test(is_administradora)
def reporte_dia(request):
    fecha_str = request.GET.get('fecha')
    
    if fecha_str:
        fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
    else:
        fecha = date.today()

    citas = Cita.objects.filter(fecha=fecha)
    return generar_pdf_reporte(f"Reporte Diario - {fecha}", citas)

# 📅 Reporte Semanal
@login_required
@user_passes_test(is_administradora) 
def reporte_semana(request):
    fecha_str = request.GET.get('fecha')
    
    if fecha_str:
        fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
    else:
        fecha = date.today()

    inicio_semana = fecha - timedelta(days=fecha.weekday())
    fin_semana = inicio_semana + timedelta(days=6)

    citas = Cita.objects.filter(fecha__range=(inicio_semana, fin_semana))
    return generar_pdf_reporte(f"Reporte Semanal - {inicio_semana} a {fin_semana}", citas)

# 🗓️ Reporte Mensual
@login_required
@user_passes_test(is_administradora)
def reporte_mes(request):
    fecha_str = request.GET.get('fecha')
    
    if fecha_str:
        fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
    else:
        fecha = date.today()

    inicio_mes = fecha.replace(day=1)
    if fecha.month == 12:
        fin_mes = fecha.replace(year=fecha.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        fin_mes = fecha.replace(month=fecha.month + 1, day=1) - timedelta(days=1)

    citas = Cita.objects.filter(fecha__range=(inicio_mes, fin_mes))
    return generar_pdf_reporte(f"Reporte Mensual - {fecha.strftime('%B %Y')}", citas)



def detalle_paciente(request, paciente_id):
    paciente = get_object_or_404(Paciente, id=paciente_id)
    return render(request, 'doctor/detalle_paciente.html', {'paciente': paciente})




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


#from django.views.decorators.csrf import csrf_exempt
#from django.http import JsonResponse

#@csrf_exempt
#def citas_por_doctor(request, doctor_id):
 #   if request.method == 'GET':
  #      citas = Cita.objects.filter(doctor_id=doctor_id).values(
   #         'id', 
    #        'paciente__nombre',  # Ajusta según relaciones en tu modelo
     #       'fecha'
      #  )
       # return JsonResponse(list(citas), safe=False)