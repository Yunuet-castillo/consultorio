
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

    # Citas de HOY
    citas_hoy = Cita.objects.filter(
        fecha=hoy
    ).order_by('hora')

    # Citas pendientes de HOY
    pendientes_hoy = citas_hoy.filter(estado='Pendiente').count()

    # Próxima cita (después de HOY)
    proxima_cita = Cita.objects.filter(
        fecha__gt=hoy
    ).order_by('fecha', 'hora').first()

    contexto = {
        'hoy': hoy,
        'citas_hoy': citas_hoy,
        'pendientes': pendientes_hoy,
        'proxima_cita': proxima_cita,
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
import os
import shutil
import pytesseract
from PyPDF2 import PdfReader
from PIL import Image as PILImage

from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.contrib import messages

from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Spacer,
    Paragraph, Image, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors

from .models import Cita, Estudio, SignosVitales
from .forms import EstudioForm


# ------------------------------------------
# ROUTE FOR TESSERACT (AUTOMATIC)
# ------------------------------------------
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# ------------------------------------------
# READ PDF
# ------------------------------------------
def leer_pdf(ruta):
    texto = ""
    with open(ruta, 'rb') as f:
        reader = PdfReader(f)
        for page in reader.pages:
            texto += page.extract_text() or ""
    return texto.strip()


# ------------------------------------------
# READ IMAGE + OCR
# ------------------------------------------
def leer_imagen(ruta):
    imagen = PILImage.open(ruta)
    texto = pytesseract.image_to_string(imagen, lang='spa')
    return texto.strip()


# ------------------------------------------
# ADD STUDY
# ------------------------------------------
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
            ext = os.path.splitext(ruta)[1].lower()

            if ext == ".pdf":
                texto = leer_pdf(ruta)
            elif ext in [".jpg", ".jpeg", ".png"]:
                texto = leer_imagen(ruta)
            else:
                texto = "Tipo de archivo no compatible."

            estudio.texto_extraido = texto
            estudio.save()

            messages.success(request, "✅ Estudio agregado correctamente.")
            form = EstudioForm()
        else:
            messages.error(request, "❌ Error en el formulario.")
    else:
        form = EstudioForm()

    return render(request, 'doctor/agregar_estudio.html', {
        'form': form,
        'paciente': paciente,
        'cita': cita
    })


# ------------------------------------------
# FOOTER
# ------------------------------------------
def pie_pagina(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 9)
    canvas.drawString(35, 25, "Hospital San Pedro — Historial Clínico")
    canvas.drawRightString(580, 25, f"Página {canvas.getPageNumber()}")
    canvas.restoreState()


# ==========================================
#      GENERAR HISTORIAL COMPLETO
# ==========================================
def imprimir_historial(request, cita_id):

    cita = get_object_or_404(Cita, id=cita_id)
    paciente = cita.paciente

    signos = SignosVitales.objects.filter(
        cita__paciente=paciente
    ).order_by('-cita__fecha')

    estudios = Estudio.objects.filter(
        paciente=paciente
    ).order_by('-fecha_subida')

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="historial_{paciente.nombre}_{cita.fecha}.pdf"'
    )

    pdf = SimpleDocTemplate(
        response,
        pagesize=letter,
        topMargin=60,
        bottomMargin=40,
        leftMargin=25,
        rightMargin=25
    )

    styles = getSampleStyleSheet()

    azul_oscuro = colors.HexColor("#1a365d")
    azul_medio = colors.HexColor("#2d5a8c")
    azul_claro = colors.HexColor("#e6f2ff")
    gris = colors.HexColor("#4a5568")

    title_style = ParagraphStyle(
        "title",
        fontSize=22,
        fontName="Helvetica-Bold",
        alignment=TA_CENTER,
        textColor=azul_oscuro,
        spaceAfter=14
    )

    section_style = ParagraphStyle(
        "section",
        fontSize=16,
        fontName="Helvetica-Bold",
        textColor=azul_medio,
        spaceBefore=20,
        spaceAfter=10,
    )

    normal = ParagraphStyle(
        "normal",
        fontSize=10,
        fontName="Helvetica",
        textColor=gris
    )

    bold = ParagraphStyle(
        "bold",
        fontSize=10,
        fontName="Helvetica-Bold",
        textColor=azul_oscuro
    )

    story = []


    # ---------------------------------------
    # HEADER
    # ---------------------------------------
    try:
        logo = Image("static/citas/img/logo.png", width=60, height=60)
        header = Table([[logo, Paragraph("<b>HOSPITAL SAN PEDRO</b>", title_style)]],
                       colWidths=[70, 420])
        header.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ]))
        story.append(header)
    except:
        story.append(Paragraph("<b>HOSPITAL SAN PEDRO</b>", title_style))

    story.append(Spacer(1, 12))
    story.append(Paragraph("HISTORIAL CLÍNICO", title_style))


    # ==========================================
    #   SIGNOS VITALES
    # ==========================================
    story.append(Paragraph("• Signos Vitales", section_style))

    if signos.exists():

        encabezados = [
            Paragraph("<b>Fecha</b>", bold),
            Paragraph("<b>Peso</b>", bold),
            Paragraph("<b>Presión</b>", bold),
            Paragraph("<b>Temp.</b>", bold),
            Paragraph("<b>F.C.</b>", bold),
            Paragraph("<b>F.R.</b>", bold),
            Paragraph("<b>Oxígeno</b>", bold)
        ]

        MAX_FILAS = 14
        filas_temp = []

        for s in signos:

            fila = [
                Paragraph(str(s.cita.fecha.strftime("%d/%m/%Y")), normal),
                Paragraph(f"{s.peso} kg" if s.peso else "—", normal),
                Paragraph(str(s.presion_arterial) if s.presion_arterial else "—", normal),
                Paragraph(f"{s.temperatura} °C" if s.temperatura else "—", normal),
                Paragraph(str(s.frecuencia_cardiaca) if s.frecuencia_cardiaca else "—", normal),
                Paragraph(str(s.frecuencia_respiratoria) if s.frecuencia_respiratoria else "—", normal),
                Paragraph(f"{s.saturacion_oxigeno}%" if s.saturacion_oxigeno else "—", normal),
            ]

            filas_temp.append(fila)

            if len(filas_temp) == MAX_FILAS:
                tabla = Table([encabezados] + filas_temp)
                tabla.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), azul_claro),
                    ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ]))
                story.append(tabla)
                story.append(PageBreak())
                filas_temp = []

        if filas_temp:
            tabla = Table([encabezados] + filas_temp)
            tabla.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), azul_claro),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ]))
            story.append(tabla)

    else:
        story.append(Paragraph("Sin registros.", normal))

    story.append(Spacer(1, 20))


    # ==========================================
    #    DIAGNÓSTICOS
    # ==========================================
    story.append(Paragraph("• Diagnósticos y Tratamientos", section_style))

    citas_paciente = Cita.objects.filter(paciente=paciente).order_by('-fecha')[:5]

    for c in citas_paciente:
        diag = c.nuevo_diagnostico or c.diagnostico or "No registrado"
        meds = c.medicamentos or "No registrado"
        ind = c.instrucciones or "No registrado"

        data = [
            [Paragraph(f"<b>Cita – {c.fecha.strftime('%d/%m/%Y')}</b>", bold)],
            [Paragraph(f"<b>Diagnóstico:</b> {diag}", normal)],
            [Paragraph(f"<b>Medicamentos:</b> {meds}", normal)],
            [Paragraph(f"<b>Indicaciones:</b> {ind}", normal)],
        ]

        tabla = Table(data, colWidths=[500])
        tabla.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), azul_claro),
            ('BOX', (0, 0), (-1, -1), 1, azul_medio),
            ('PADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(tabla)
        story.append(Spacer(1, 15))


    # ==========================================
    #        ESTUDIOS
    # ==========================================
    story.append(Paragraph("• Estudios y Análisis", section_style))

    for e in estudios[:4]:
        fecha_est = e.fecha_subida.strftime('%d/%m/%Y %H:%M')

        data = [
            [Paragraph(f"<b>Estudio – {fecha_est}</b>", bold)],
            [Paragraph(f"<b>Descripción:</b> {e.descripcion or 'Sin descripción'}", normal)],
            [Paragraph(f"<b>Texto extraído:</b> {e.texto_extraido or '(Sin texto)'}", normal)],
        ]

        tabla = Table(data, colWidths=[500])
        tabla.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), azul_claro),
            ('BOX', (0, 0), (-1, -1), 1, azul_medio),
            ('PADDING', (0, 0), (-1, -1), 8),
        ]))

        story.append(tabla)
        story.append(Spacer(1, 10))

        # Insert image if exists
        ruta = e.archivo.path
        ext = os.path.splitext(ruta)[1].lower()

        if ext in ['.jpg', '.jpeg', '.png']:
            try:
                story.append(Image(ruta, width=280, height=200, kind='proportional'))
            except:
                story.append(Paragraph("(No se pudo cargar la imagen)", normal))

        story.append(Spacer(1, 20))


    # ==========================================
    # BUILD PDF
    # ==========================================
    pdf.build(story, onFirstPage=pie_pagina, onLaterPages=pie_pagina)

    messages.success(request, "PDF creado con éxito.")
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

    # Guardar diagnóstico nuevo
    if request.method == "POST":
        texto = request.POST.get("diagnostico", "").strip()

        if texto:
            # Guardar en histórico
            DiagnosticoHistorico.objects.create(
                cita=cita,
                doctor=request.user,
                texto=texto
            )

            # Actual — guardar en Cita
            cita.diagnostico = texto
            cita.save()

            messages.success(request, "Diagnóstico actualizado correctamente.")
            return redirect("detalle_cita_doctor", cita_id=cita.id)

    # Signos vitales
    signos = getattr(cita, "signosvitales", None)
    receta = getattr(cita, "receta", None)

    # Nuevo: historial REAL de diagnósticos
    historial = DiagnosticoHistorico.objects.filter(
        cita=cita
    ).order_by("-fecha")

    contexto = {
        "cita": cita,
        "paciente": cita.paciente,
        "signos": signos,
        "receta": receta,

        # Nuevo
        "historial": historial,
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
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    )
    from reportlab.lib import colors

    cita = get_object_or_404(Cita, id=cita_id)
    receta = getattr(cita, 'receta', None)

    if not receta:
        messages.error(request, "❌ No hay receta para esta cita.")
        return redirect('detalle_cita_doctor', cita_id=cita.id)

    paciente = cita.paciente
    doctor = cita.doctor

    cita.estado = "Atendida"
    cita.save()

    # SIGNOS VITALES
    from .models import SignosVitales
    signos = SignosVitales.objects.filter(cita=cita).first()

    if not signos:
        class Empty:
            temperatura = presion_arterial = frecuencia_cardiaca = None
            frecuencia_respiratoria = saturacion_oxigeno = peso = None
        signos = Empty()

    # PDF SETUP
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        leftMargin=25,
        rightMargin=25,
        topMargin=30,
        bottomMargin=25
    )

    elements = []
    styles = getSampleStyleSheet()

    # Colores
    azul_oscuro = colors.HexColor("#0d47a1")
    azul_medio = colors.HexColor("#1976d2")
    gris_medio = colors.HexColor("#424242")
    blanco = colors.HexColor("#ffffff")

    # Datos fijos
    CEDULA_DEF = "8025534"
    ESPECIALIDAD_DEF = "Ginecología, Obstetricia, Medicina Materno-Fetal"
    HOSPITAL_NOMBRE = "Hospital San Pedro"

    # -----------------------------
    # ENCABEZADO AJUSTADO
    # -----------------------------
    from django.conf import settings
    logo_path = os.path.join(settings.BASE_DIR, "static", "citas", "img", "logo.png")

    # Título hospital con más separación
    titulo_hospital = Paragraph(
        f"<b>{HOSPITAL_NOMBRE}</b>",
        ParagraphStyle(
            "titulo_hospital",
            fontSize=18,
            alignment=TA_CENTER,
            textColor=azul_oscuro,
            spaceAfter=10     # 👈 SEPARACIÓN AUMENTADA
        )
    )

    # “RECETA MÉDICA” más separado
    titulo_receta = Paragraph(
        "<b><font size='13' color='#1976d2'>RECETA MÉDICA</font></b>",
        ParagraphStyle(
            "titulo_receta",
            fontSize=13,
            alignment=TA_CENTER,
            spaceBefore=6,    # 👈 SEPARACIÓN AUMENTADA
            spaceAfter=6
        )
    )

    contacto = Paragraph(f"""
<b>Av. 5 de Mayo Sur Nº 29</b><br/>
Zacapoaxtla, Pue.<br/>
<b>Tel:</b> 233 314 3084<br/>
<b>Fecha:</b> {cita.fecha.strftime('%d/%m/%Y')}
""", ParagraphStyle('contacto', fontSize=8, alignment=TA_RIGHT))

    if os.path.exists(logo_path):
        logo = Image(logo_path, width=70, height=70)
        header = Table([
            [logo, titulo_hospital, contacto],
            ["", titulo_receta, ""]
        ], colWidths=[80, 450, 180])
    else:
        header = Table([
            [titulo_hospital, contacto],
            [titulo_receta, ""]
        ], colWidths=[530, 180])

    header.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('ALIGN', (1, 1), (1, 1), 'CENTER'),
        ('SPAN', (1, 1), (1, 1)),
    ]))

    elements.append(header)
    elements.append(Spacer(1, 12))

    # ---------------------------------------
    # INFO DEL PACIENTE
    # ---------------------------------------
    paciente_nombre = f"{paciente.nombre} {paciente.apellido_paterno} {paciente.apellido_materno or ''}"
    fecha_nac = getattr(paciente, 'fecha_nacimiento', None)
    fecha_nac_str = fecha_nac.strftime('%d/%m/%Y') if fecha_nac else "---"

    subtitulo_estilo = ParagraphStyle(
        'Subtitulo',
        fontName="Helvetica-Bold",
        fontSize=11,
        textColor=blanco,
        leading=13
    )

    label_estilo = ParagraphStyle(
        'Label',
        fontName="Helvetica-Bold",
        fontSize=9,
        textColor=azul_oscuro
    )

    normal_estilo = ParagraphStyle(
        'Normal',
        fontName="Helvetica",
        fontSize=9,
        textColor=gris_medio,
        leading=12
    )

    info_data = [
        [
            Paragraph("INFORMACIÓN DEL PACIENTE", subtitulo_estilo),
            Paragraph("DATOS MÉDICOS", subtitulo_estilo)
        ],
        [
            Table([
                ["Nombre:", paciente_nombre],
                ["Edad:", f"{paciente.edad} años"],
                ["Fecha nac.:", fecha_nac_str]
            ], colWidths=[80, 250]),

            Table([
                ["Médico:", f"Dr. {doctor.user.get_full_name()}"],
                ["Especialidad:", ESPECIALIDAD_DEF],
                ["Cédula:", CEDULA_DEF]
            ], colWidths=[80, 250])
        ]
    ]

    info_table = Table(info_data, colWidths=[355, 355])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), azul_medio),
        ('BOX', (0, 0), (-1, -1), 1.5, azul_oscuro)
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 10))

    # ---------------------------------------
    # SIGNOS VITALES
    # ---------------------------------------
    signos_vitales_data = [
        [
            Paragraph("SIGNOS VITALES", subtitulo_estilo),
            Paragraph("SIGNOS VITALES", subtitulo_estilo)
        ],
        [
            Table([
                ["Temperatura:", f"{signos.temperatura or '---'} °C"],
                ["Presión:", signos.presion_arterial or '---'],
                ["F. Cardíaca:", f"{signos.frecuencia_cardiaca or '---'} lpm"]
            ], colWidths=[85, 140]),

            Table([
                ["F. Respiratoria:", f"{signos.frecuencia_respiratoria or '---'} rpm"],
                ["Sat. O2:", f"{signos.saturacion_oxigeno or '---'}%"],
                ["Peso:", f"{signos.peso or '---'} kg"]
            ], colWidths=[85, 140])
        ]
    ]

    signos_vitales_table = Table(signos_vitales_data, colWidths=[355, 355])
    signos_vitales_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), azul_medio),
        ('BOX', (0, 0), (-1, -1), 1.5, azul_oscuro)
    ]))
    elements.append(signos_vitales_table)
    elements.append(Spacer(1, 10))

    # ---------------------------------------
    # DIAGNÓSTICO
    # ---------------------------------------
    if cita.diagnostico:
        diag_table = Table([
            [Paragraph("DIAGNÓSTICO", subtitulo_estilo)],
            [Paragraph(cita.diagnostico.replace("\n", "<br/>"), normal_estilo)]
        ], colWidths=[710])

        diag_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), azul_medio),
            ('BOX', (0, 0), (-1, -1), 1.5, azul_oscuro)
        ]))

        elements.append(diag_table)
        elements.append(Spacer(1, 12))

    # ---------------------------------------
    # MEDICAMENTOS / INDICACIONES
    # ---------------------------------------
    medicamentos_texto = (receta.medicamentos or "").replace("\n", "<br/>")
    indicaciones_texto = (receta.indicaciones or "").replace("\n", "<br/>")

    contenido_data = [
        [
            Paragraph("MEDICAMENTOS PRESCRITOS", subtitulo_estilo),
            Paragraph("INDICACIONES MÉDICAS", subtitulo_estilo)
        ],
        [
            Paragraph(medicamentos_texto or "<i>No se prescribieron medicamentos</i>", normal_estilo),
            Paragraph(indicaciones_texto or "<i>No hay indicaciones específicas</i>", normal_estilo)
        ]
    ]

    contenido_table = Table(contenido_data, colWidths=[355, 355])
    contenido_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), azul_medio),
        ('BOX', (0, 0), (-1, -1), 1.5, azul_oscuro)
    ]))
    elements.append(contenido_table)
    elements.append(Spacer(1, 38))

    # ---------------------------------------
    # FIRMA
    # ---------------------------------------
    firma = [
        [Spacer(1, 25)],
        [Paragraph(
            "<para alignment='center'>__________________________________________</para>",
            ParagraphStyle("linea", fontSize=16, leading=18)
        )],
        [Spacer(1, 6)],
        [Paragraph(
            f"<b>Dr. {doctor.user.get_full_name()}</b>",
            ParagraphStyle("firma_nom", fontSize=12, alignment=TA_CENTER)
        )],
        [Paragraph(
            f"Cédula Profesional: {CEDULA_DEF}",
            ParagraphStyle("firma_cedula", fontSize=10, alignment=TA_CENTER)
        )],
        [Paragraph(
            f"{ESPECIALIDAD_DEF}",
            ParagraphStyle("firma_esp", fontSize=10, alignment=TA_CENTER)
        )]
    ]

    firma_tabla = Table(firma, colWidths=[710])
    firma_tabla.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER')
    ]))

    elements.append(firma_tabla)

    # ---------------------------------------
    # FOOTER
    # ---------------------------------------
    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica-Bold", 7)
        canvas.setFillColor(azul_oscuro)
        canvas.drawString(25, 16, f"{HOSPITAL_NOMBRE} - Receta Médica Oficial")
        canvas.restoreState()

    doc.build(elements, onFirstPage=footer, onLaterPages=footer)

    pdf = buffer.getvalue()
    buffer.close()

    response = HttpResponse(pdf, content_type="application/pdf")
    response['Content-Disposition'] = (
        f'attachment; filename=\"receta_medica_{paciente.nombre}_{cita.fecha.strftime('%Y%m%d')}\".pdf"')
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


def actualizar_citas(request):
    doctor = request.user.doctor
    hoy = date.today()

    citas = Cita.objects.filter(
        doctor=doctor,
        fecha=hoy  # ← SOLO citas del día actual
    ).order_by("hora")

    return render(request, "doctor/partials/tabla_citas.html", {"citas": citas})



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