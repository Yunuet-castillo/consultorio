
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
from reportlab.platypus.flowables import HRFlowable
@login_required
@user_passes_test(is_doctor)
def imprimir_historial(request, cita_id):
    cita_actual = get_object_or_404(Cita, id=cita_id)
    paciente = cita_actual.paciente
    citas = Cita.objects.filter(paciente=paciente).order_by('-fecha')

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="historial_{paciente.nombre}_{date.today()}.pdf"'
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

    subtitle_style = ParagraphStyle(
        "subtitle",
        fontSize=12,
        fontName="Helvetica",
        alignment=TA_CENTER,
        textColor=gris,
        spaceAfter=20
    )

    section_style = ParagraphStyle(
        "section",
        fontSize=16,
        fontName="Helvetica-Bold",
        textColor=azul_medio,
        spaceBefore=30,
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

    info_style = ParagraphStyle(
        "info",
        fontSize=11,
        fontName="Helvetica",
        textColor=azul_oscuro,
        spaceAfter=5
    )

    story = []

    # ========== ENCABEZADO MEJORADO ==========
    try:
        logo = Image("static/citas/img/logo.png", width=70, height=70)
        # Tabla para organizar logo y texto
        header_data = [
            [logo, 
             Paragraph("<b>HOSPITAL SAN PEDRO</b><br/><font size='10'>Centro Médico Especializado</font>", 
                      ParagraphStyle(
                          "hospital_name",
                          fontSize=18,
                          fontName="Helvetica-Bold",
                          textColor=azul_oscuro,
                          alignment=TA_CENTER,
                          spaceAfter=0
                      ))]
        ]
        header_table = Table(header_data, colWidths=[80, 450])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, 0), 'CENTER'),
            ('ALIGN', (1, 0), (1, 0), 'CENTER'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(header_table)
    except:
        story.append(Paragraph("<b>HOSPITAL SAN PEDRO</b>", title_style))

    story.append(Spacer(1, 5))
    
    # Línea divisoria
    story.append(HRFlowable(
        width="100%",
        thickness=1,
        color=azul_medio,
        spaceBefore=5,
        spaceAfter=10
    ))
    
    story.append(Paragraph("HISTORIAL CLÍNICO", title_style))
    story.append(Paragraph("Documento confidencial - Uso médico exclusivo", subtitle_style))

    # ========== INFORMACIÓN DEL PACIENTE Y DOCTOR ==========
    patient_info = Table([
        [Paragraph(f"<b>PACIENTE:</b>", bold), 
         Paragraph(f"{paciente.nombre} {paciente.apellido_paterno} {paciente.apellido_materno or ''}", info_style)],
        [Paragraph(f"<b>DOCTOR:</b>", bold), 
         Paragraph(f"Dr. {cita_actual.doctor.user.nombre} {cita_actual.doctor.user.apellido_paterno} {cita_actual.doctor.user.apellido_materno or ''}", info_style)],
        [Paragraph(f"<b>FECHA DE GENERACIÓN:</b>", bold), 
         Paragraph(f"{date.today().strftime('%d/%m/%Y')}", info_style)],
    ], colWidths=[120, 380])
    
    patient_info.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
    ]))
    
    story.append(patient_info)
    story.append(Spacer(1, 20))

    # ========== HISTORIAL POR BLOQUES ==========
    for c in citas:
        story.append(Paragraph(f"Cita del {c.fecha.strftime('%d/%m/%Y')}", section_style))
        
        # Doctor de esta cita específica
        story.append(Paragraph(
            f"<b>Atendió:</b> Dr. {c.doctor.user.nombre} {c.doctor.user.apellido_paterno} {c.doctor.user.apellido_materno or ''}",
            normal
        ))
        story.append(Spacer(1, 10))

        bloque = []

        # ---------- Signos Vitales ----------
        try:
            sv = SignosVitales.objects.get(cita=c)
        except SignosVitales.DoesNotExist:
            sv = None

        if sv:
            bloque.append(Paragraph("<b>Signos Vitales</b>", bold))
            signos_table = Table([
                [Paragraph("Peso:", normal), Paragraph(f"{sv.peso or '—'} kg", normal),
                 Paragraph("Presión:", normal), Paragraph(f"{sv.presion_arterial or '—'}", normal)],
                [Paragraph("Temperatura:", normal), Paragraph(f"{sv.temperatura or '—'} °C", normal),
                 Paragraph("Frec. Cardiaca:", normal), Paragraph(f"{sv.frecuencia_cardiaca or '—'}", normal)],
                [Paragraph("Frec. Respiratoria:", normal), Paragraph(f"{sv.frecuencia_respiratoria or '—'}", normal),
                 Paragraph("Saturación O₂:", normal), Paragraph(f"{sv.saturacion_oxigeno or '—'}%", normal)],
            ], colWidths=[100, 80, 100, 80])
            signos_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ]))
            bloque.append(signos_table)
            bloque.append(Spacer(1, 10))

        # ---------- Diagnóstico ----------
        diagnostico = c.nuevo_diagnostico or c.diagnostico or "No registrado"
        bloque.append(Paragraph("<b>Diagnóstico</b>", bold))
        bloque.append(Paragraph(diagnostico, normal))
        bloque.append(Spacer(1, 10))

        # ---------- Medicamentos e indicaciones ----------
        receta = getattr(c, "receta", None)

        meds = receta.medicamentos if receta else "No registrado"
        ind = receta.indicaciones if receta else "No registrado"

        bloque.append(Paragraph("<b>Medicamentos</b>", bold))
        bloque.append(Paragraph(meds, normal))
        bloque.append(Spacer(1, 10))

        bloque.append(Paragraph("<b>Indicaciones</b>", bold))
        bloque.append(Paragraph(ind, normal))
        bloque.append(Spacer(1, 15))

        # ---------- Estudios del mismo día ----------
        estudios = Estudio.objects.filter(
            paciente=paciente,
            fecha_subida__date=c.fecha
        )

        if estudios.exists():
            bloque.append(Paragraph("<b>Estudios y Análisis</b>", bold))

            for e in estudios:
                bloque.append(Paragraph(f"Descripción: {e.descripcion or 'Sin descripción'}", normal))
                bloque.append(Paragraph(f"Texto extraído: {e.texto_extraido or '(Sin texto)'}", normal))

                ruta = e.archivo.path
                ext = os.path.splitext(ruta)[1].lower()

                if ext in ['.jpg', '.jpeg', '.png']:
                    try:
                        bloque.append(Image(ruta, width=280, height=200, kind='proportional'))
                    except:
                        bloque.append(Paragraph("(No se pudo cargar la imagen)", normal))

                bloque.append(Spacer(1, 15))

        # ===== BLOQUE COMPLETO =====
        marco = Table([[b] for b in bloque], colWidths=[500])
        marco.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 1, azul_medio),
            ('BACKGROUND', (0, 0), (-1, 0), azul_claro),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (0, 0), 12),
            ('BOTTOMPADDING', (0, 0), (0, 0), 12),
        ]))

        story.append(marco)
        story.append(Spacer(1, 25))

    # ========== GENERAR PDF ==========
    pdf.build(story)

    messages.success(request, "Historial descargado correctamente.")
    return response


@login_required
@user_passes_test(lambda u: u.is_authenticated)
def imprimir_historial_paciente(request, paciente_id):
    paciente = get_object_or_404(Paciente, id=paciente_id)
    citas = Cita.objects.filter(paciente=paciente).order_by('-fecha')

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="historial_{paciente.nombre}_{date.today()}.pdf"'
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

    subtitle_style = ParagraphStyle(
        "subtitle",
        fontSize=12,
        fontName="Helvetica",
        alignment=TA_CENTER,
        textColor=gris,
        spaceAfter=20
    )

    section_style = ParagraphStyle(
        "section",
        fontSize=16,
        fontName="Helvetica-Bold",
        textColor=azul_medio,
        spaceBefore=30,
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

    info_style = ParagraphStyle(
        "info",
        fontSize=11,
        fontName="Helvetica",
        textColor=azul_oscuro,
        spaceAfter=5
    )

    story = []

    # ========== ENCABEZADO MEJORADO ==========
    try:
        logo = Image("static/citas/img/logo.png", width=70, height=70)
        # Tabla para organizar logo y texto
        header_data = [
            [logo, 
             Paragraph("<b>HOSPITAL SAN PEDRO</b><br/><font size='10'>Centro Médico Especializado</font>", 
                      ParagraphStyle(
                          "hospital_name",
                          fontSize=18,
                          fontName="Helvetica-Bold",
                          textColor=azul_oscuro,
                          alignment=TA_CENTER,
                          spaceAfter=0
                      ))]
        ]
        header_table = Table(header_data, colWidths=[80, 450])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, 0), 'CENTER'),
            ('ALIGN', (1, 0), (1, 0), 'CENTER'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(header_table)
    except:
        story.append(Paragraph("<b>HOSPITAL SAN PEDRO</b>", title_style))

    story.append(Spacer(1, 5))
    
    # Línea divisoria
    story.append(HRFlowable(
        width="100%",
        thickness=1,
        color=azul_medio,
        spaceBefore=5,
        spaceAfter=10
    ))
    
    story.append(Paragraph("HISTORIAL CLÍNICO", title_style))
    story.append(Paragraph("Documento confidencial - Uso médico exclusivo", subtitle_style))

    # ========== INFORMACIÓN DEL PACIENTE ==========
    patient_info = Table([
        [Paragraph(f"<b>PACIENTE:</b>", bold), 
         Paragraph(f"{paciente.nombre} {paciente.apellido_paterno} {paciente.apellido_materno or ''}", info_style)],
        [Paragraph(f"<b>FECHA DE GENERACIÓN:</b>", bold), 
         Paragraph(f"{date.today().strftime('%d/%m/%Y')}", info_style)],
        [Paragraph(f"<b>TOTAL DE CONSULTAS:</b>", bold), 
         Paragraph(f"{citas.count()} consulta(s)", info_style)],
    ], colWidths=[120, 380])
    
    patient_info.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
    ]))
    
    story.append(patient_info)
    story.append(Spacer(1, 20))

    # ========== HISTORIAL POR BLOQUES ==========
    for cita in citas:
        story.append(Paragraph(f"Cita del {cita.fecha.strftime('%d/%m/%Y')}", section_style))
        
        # Doctor de esta cita específica
        story.append(Paragraph(
            f"<b>Atendió:</b> Dr. {cita.doctor.user.nombre} {cita.doctor.user.apellido_paterno} {cita.doctor.user.apellido_materno or ''}",
            normal
        ))
        story.append(Spacer(1, 10))

        bloque = []

        # ---------- Signos Vitales ----------
        try:
            sv = SignosVitales.objects.get(cita=cita)
        except SignosVitales.DoesNotExist:
            sv = None

        if sv:
            bloque.append(Paragraph("<b>Signos Vitales</b>", bold))
            signos_table = Table([
                [Paragraph("Peso:", normal), Paragraph(f"{sv.peso or '—'} kg", normal),
                 Paragraph("Presión:", normal), Paragraph(f"{sv.presion_arterial or '—'}", normal)],
                [Paragraph("Temperatura:", normal), Paragraph(f"{sv.temperatura or '—'} °C", normal),
                 Paragraph("Frec. Cardiaca:", normal), Paragraph(f"{sv.frecuencia_cardiaca or '—'}", normal)],
                [Paragraph("Frec. Respiratoria:", normal), Paragraph(f"{sv.frecuencia_respiratoria or '—'}", normal),
                 Paragraph("Saturación O₂:", normal), Paragraph(f"{sv.saturacion_oxigeno or '—'}%", normal)],
            ], colWidths=[100, 80, 100, 80])
            signos_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ]))
            bloque.append(signos_table)
            bloque.append(Spacer(1, 10))

        # ---------- Diagnóstico ----------
        diagnostico = cita.nuevo_diagnostico or cita.diagnostico or "No registrado"
        bloque.append(Paragraph("<b>Diagnóstico</b>", bold))
        bloque.append(Paragraph(diagnostico, normal))
        bloque.append(Spacer(1, 10))

        # ---------- Medicamentos e indicaciones ----------
        receta = getattr(cita, "receta", None)

        meds = receta.medicamentos if receta else "No registrado"
        ind = receta.indicaciones if receta else "No registrado"

        bloque.append(Paragraph("<b>Medicamentos</b>", bold))
        bloque.append(Paragraph(meds, normal))
        bloque.append(Spacer(1, 10))

        bloque.append(Paragraph("<b>Indicaciones</b>", bold))
        bloque.append(Paragraph(ind, normal))
        bloque.append(Spacer(1, 15))

        # ---------- Estudios del mismo día ----------
        estudios = Estudio.objects.filter(
            paciente=paciente,
            fecha_subida__date=cita.fecha
        )

        if estudios.exists():
            bloque.append(Paragraph("<b>Estudios y Análisis</b>", bold))

            for estudio in estudios:
                bloque.append(Paragraph(f"Descripción: {estudio.descripcion or 'Sin descripción'}", normal))
                bloque.append(Paragraph(f"Texto extraído: {estudio.texto_extraido or '(Sin texto)'}", normal))

                ruta = estudio.archivo.path
                ext = os.path.splitext(ruta)[1].lower()

                if ext in ['.jpg', '.jpeg', '.png']:
                    try:
                        bloque.append(Image(ruta, width=280, height=200, kind='proportional'))
                    except:
                        bloque.append(Paragraph("(No se pudo cargar la imagen)", normal))

                bloque.append(Spacer(1, 15))

        # ===== BLOQUE COMPLETO =====
        marco = Table([[b] for b in bloque], colWidths=[500])
        marco.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 1, azul_medio),
            ('BACKGROUND', (0, 0), (-1, 0), azul_claro),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (0, 0), 12),
            ('BOTTOMPADDING', (0, 0), (0, 0), 12),
        ]))

        story.append(marco)
        story.append(Spacer(1, 25))

    # ========== GENERAR PDF ==========
    pdf.build(story)
    
    messages.success(request, "Historial descargado correctamente.")
    return response

# ---------------------------
# --- Gestión de Pacientes y Citas ---
# ---------------------------
@login_required(login_url='login')
def agendar_paciente_existente(request, paciente_id):

    if request.user.role not in ['doctor', 'administradora']:
        return redirect('dashboard')

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


@login_required(login_url='login')
def agendar_cita(request):

    # 🔐 SOLO DOCTOR Y ADMINISTRADORA
    if request.user.role not in ['doctor', 'administradora']:
        return redirect('dashboard')

    paciente_id = request.session.get('paciente_id')
    paciente = None

    from .models import Paciente, Doctor

    if paciente_id:
        paciente = Paciente.objects.filter(id=paciente_id).first()

    doctores = Doctor.objects.all()

    if request.method == 'POST':
        form = CitaForm(request.POST, paciente=paciente)
        form.fields['doctor_user'].queryset = doctores

        if form.is_valid():
            form.save()
            messages.success(request, '✅ La cita ha sido agendada con éxito.')

            # Limpiar sesión
            request.session.pop('paciente_id', None)

            # 🔁 REDIRECCIÓN SEGÚN ROL
            if request.user.role == 'doctor':
                return redirect('dashboard_doctor')
            else:
                return redirect('dashboard_administradora')

        else:
            messages.error(request, '❌ Revisa los datos del formulario')

    else:
        form = CitaForm(paciente=paciente)
        form.fields['doctor_user'].queryset = doctores

    return render(request, 'recepcion/agendar_cita.html', {
        'form': form,
        'paciente': paciente,
        'titulo': 'Agendar Cita',
        'boton': 'Agendar',
    })







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
def puede_registrar_signos(user):
    return hasattr(user, 'enfermera') or hasattr(user, 'doctor')


@login_required
@user_passes_test(puede_registrar_signos)
def registrar_signos_vitales(request, cita_id):
    cita = get_object_or_404(Cita, id=cita_id)

    # Obtener signos si ya existen (edición)
    signos_vitales = SignosVitales.objects.filter(cita=cita).first()

    if request.method == 'POST':
        form = SignosVitalesForm(request.POST, instance=signos_vitales)

        if form.is_valid():
            signos = form.save(commit=False)
            signos.cita = cita
            signos.save()

            messages.success(request, "✅ Signos vitales guardados correctamente.")
            return redirect('detalle_cita_doctor', cita.id)
        else:
            messages.error(request, "❌ Revisa los datos ingresados.")
    else:
        form = SignosVitalesForm(instance=signos_vitales)

    contexto = {
        'form': form,
        'cita': cita,
        'signos': signos_vitales,
    }

    return render(request, 'doctor/registrar_signos_vitales.html', contexto)


# ---------------------------
# --- Gestión de Diagnóstico y Recetas ---
# ---------------------------


# ---------------------------
# Detalle de la cita para doctor
# ---------------------------
@login_required
@user_passes_test(is_doctor)
def detalle_cita_doctor(request, cita_id):

    cita = get_object_or_404(
        Cita.objects.select_related('paciente'),
        id=cita_id
    )

    # GUARDAR DIAGNÓSTICO, MEDICAMENTOS E INDICACIONES
    if request.method == "POST":
        texto = request.POST.get("diagnostico", "").strip()
        meds = request.POST.get("medicamentos", "").strip()
        instrucciones = request.POST.get("instrucciones", "").strip()

        if texto:
            # Guardar en historial real
            DiagnosticoHistorico.objects.create(
                cita=cita,
                doctor=request.user,
                texto=texto
            )

            # Guardar en la cita
            cita.diagnostico = texto
            cita.medicamentos = meds
            cita.instrucciones = instrucciones
            cita.save()

            messages.success(request, "Diagnóstico actualizado correctamente.")
            return redirect("detalle_cita_doctor", cita_id=cita.id)

    signos = getattr(cita, "signosvitales", None)
    receta = getattr(cita, "receta", None)

    # historial REAL de diagnósticos
    historial = DiagnosticoHistorico.objects.filter(
        cita=cita
    ).order_by("-fecha")

    contexto = {
        "cita": cita,
        "paciente": cita.paciente,
        "signos": signos,
        "receta": receta,
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
    from reportlab.lib.pagesizes import portrait, letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT, TA_JUSTIFY
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    )
    from reportlab.lib import colors
    from reportlab.lib.units import inch

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
    
    # Márgenes ajustados para mejor uso del espacio
    doc = SimpleDocTemplate(
        buffer,
        pagesize=portrait(letter),
        leftMargin=0.3 * inch,
        rightMargin=0.3 * inch,
        topMargin=0.2 * inch,
        bottomMargin=0.2 * inch
    )

    elements = []
    styles = getSampleStyleSheet()

    # Colores
    azul_oscuro = colors.HexColor("#0d47a1")
    azul_medio = colors.HexColor("#1976d2")
    gris_medio = colors.HexColor("#424242")
    gris_claro = colors.HexColor("#757575")
    blanco = colors.HexColor("#ffffff")

    # Datos fijos
    CEDULA_DEF = "8025534"
    ESPECIALIDAD_DEF = "Ginecología, Obstetricia, Medicina Materno-Fetal"
    HOSPITAL_NOMBRE = "Hospital San Pedro"

    # -----------------------------
    # ENCABEZADO DISTRIBUIDO
    # -----------------------------
    from django.conf import settings
    logo_path = os.path.join(settings.BASE_DIR, "static", "citas", "img", "logo.png")
    
    # Encabezado en 3 columnas: logo, título, contacto
    header_data = []
    
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=35, height=35)  # Logo un poco más grande
        fila = [
            logo,
            Paragraph(
                f"<font size='11'><b>{HOSPITAL_NOMBRE}</b></font><br/>"
                f"<font size='9' color='#1976d2'><b>RECETA MÉDICA</b></font>",
                ParagraphStyle("titulo", fontSize=11, textColor=azul_oscuro, alignment=TA_CENTER)
            ),
            Paragraph(
                f"<font size='7'><b>Av. 5 de Mayo Sur Nº 29</b></font><br/>"
                f"<font size='7'>Zacapoaxtla, Pue.</font><br/>"
                f"<font size='7'><b>Tel:</b> 233 314 3084</font><br/>"
                f"<font size='7'><b>Fecha:</b> {cita.fecha.strftime('%d/%m/%Y')}</font>",
                ParagraphStyle('contacto', fontSize=7, alignment=TA_RIGHT)
            )
        ]
        col_widths = [0.7*inch, 5.0*inch, 2.3*inch]
    else:
        fila = [
            Paragraph(
                f"<font size='12'><b>{HOSPITAL_NOMBRE}</b></font><br/>"
                f"<font size='10' color='#1976d2'><b>RECETA MÉDICA</b></font>",
                ParagraphStyle("titulo", fontSize=12, textColor=azul_oscuro, alignment=TA_CENTER)
            ),
            "",
            Paragraph(
                f"<font size='7'><b>Av. 5 de Mayo Sur Nº 29</b></font><br/>"
                f"<font size='7'>Zacapoaxtla, Pue.</font><br/>"
                f"<font size='7'><b>Tel:</b> 233 314 3084</font><br/>"
                f"<font size='7'><b>Fecha:</b> {cita.fecha.strftime('%d/%m/%Y')}</font>",
                ParagraphStyle('contacto', fontSize=7, alignment=TA_RIGHT)
            )
        ]
        col_widths = [4.0*inch, 1.0*inch, 3.0*inch]
    
    header_data.append(fila)
    
    header_table = Table(header_data, colWidths=col_widths)
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    
    elements.append(header_table)
    
    # Línea separadora
    elements.append(Spacer(1, 2))
    linea = Table([['']], colWidths=[7.9*inch], rowHeights=[1])
    linea.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (-1, -1), 1, azul_oscuro),
        ('LINEABOVE', (0, 0), (-1, -1), 0.5, colors.lightgrey),
    ]))
    elements.append(linea)
    elements.append(Spacer(1, 8))

    # ---------------------------------------
    # INFORMACIÓN DISTRIBUIDA - COMO EN LA IMAGEN
    # ---------------------------------------
    paciente_nombre = f"{paciente.nombre} {paciente.apellido_paterno} {paciente.apellido_materno or ''}"
    fecha_nac = getattr(paciente, 'fecha_nacimiento', None)
    fecha_nac_str = fecha_nac.strftime('%d/%m/%Y') if fecha_nac else "---"
    
    # Tabla con 2 columnas principales (Paciente y Médico)
    # Primera fila: Títulos
    # Segunda fila: Valores alineados
    
    info_data = [
        # Fila 1: Títulos
        [
            Paragraph("<font size='8'><b>PACIENTE:</b></font>", 
                     ParagraphStyle('label', fontSize=8, textColor=azul_oscuro, alignment=TA_LEFT)),
            Paragraph("<font size='8'><b>EDAD:</b></font>", 
                     ParagraphStyle('label', fontSize=8, textColor=azul_oscuro, alignment=TA_LEFT)),
            Paragraph("<font size='8'><b>FECHA NAC.:</b></font>", 
                     ParagraphStyle('label', fontSize=8, textColor=azul_oscuro, alignment=TA_LEFT)),
            "",  # Espacio para alinear con la segunda columna
            Paragraph("<font size='8'><b>MÉDICO:</b></font>", 
                     ParagraphStyle('label', fontSize=8, textColor=azul_oscuro, alignment=TA_LEFT)),
            Paragraph("<font size='8'><b>ESPECIALIDAD:</b></font>", 
                     ParagraphStyle('label', fontSize=8, textColor=azul_oscuro, alignment=TA_LEFT)),
            Paragraph("<font size='8'><b>CÉDULA:</b></font>", 
                     ParagraphStyle('label', fontSize=8, textColor=azul_oscuro, alignment=TA_LEFT)),
        ],
        # Fila 2: Valores
        [
            Paragraph(f"<font size='8'>{paciente_nombre}</font>", 
                     ParagraphStyle('value', fontSize=8, textColor=gris_medio, alignment=TA_LEFT)),
            Paragraph(f"<font size='8'>{paciente.edad} años</font>", 
                     ParagraphStyle('value', fontSize=8, textColor=gris_medio, alignment=TA_LEFT)),
            Paragraph(f"<font size='8'>{fecha_nac_str}</font>", 
                     ParagraphStyle('value', fontSize=8, textColor=gris_medio, alignment=TA_LEFT)),
            Spacer(1, 0.1*inch),  # Espaciador
            Paragraph(f"<font size='8'>Dr. {doctor.user.get_full_name()}</font>", 
                     ParagraphStyle('value', fontSize=8, textColor=gris_medio, alignment=TA_LEFT)),
            Paragraph(f"<font size='7'>{ESPECIALIDAD_DEF}</font>", 
                     ParagraphStyle('value', fontSize=7, textColor=gris_medio, alignment=TA_LEFT)),
            Paragraph(f"<font size='8'>{CEDULA_DEF}</font>", 
                     ParagraphStyle('value', fontSize=8, textColor=gris_medio, alignment=TA_LEFT)),
        ]
    ]
    
    # Anchos de columna optimizados para distribución
    col_widths_info = [1.8*inch, 0.7*inch, 1.0*inch, 0.5*inch, 1.8*inch, 1.5*inch, 0.8*inch]
    
    info_table = Table(info_data, colWidths=col_widths_info)
    info_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 0), (2, 0), 0.5, colors.lightgrey),
        ('LINEBELOW', (4, 0), (-1, 0), 0.5, colors.lightgrey),
        ('LINEBELOW', (0, 1), (2, 1), 0.5, colors.lightgrey),
        ('LINEBELOW', (4, 1), (-1, 1), 0.5, colors.lightgrey),
        ('SPAN', (3, 0), (3, 1)),  # Espaciador ocupa ambas filas
    ]))
    
    elements.append(info_table)
    elements.append(Spacer(1, 12))

    # ---------------------------------------
    # SIGNOS VITALES - TABLA COMPACTA
    # ---------------------------------------
    signos_header = Table([['SIGNOS VITALES']], colWidths=[7.9*inch])
    signos_header.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), azul_medio),
        ('TEXTCOLOR', (0, 0), (-1, -1), blanco),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOLD', (0, 0), (-1, -1), 1),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(signos_header)
    
    # Tabla de signos vitales en 2 filas compactas
    signos_data = [
        [
            Paragraph("<font size='7'>Temperatura:</font>", ParagraphStyle('label', fontSize=7, textColor=gris_claro)),
            Paragraph(f"<font size='8'>{signos.temperatura or '---'} °C</font>", ParagraphStyle('value', fontSize=8, textColor=gris_medio)),
            Paragraph("<font size='7'>Presión arterial:</font>", ParagraphStyle('label', fontSize=7, textColor=gris_claro)),
            Paragraph(f"<font size='8'>{signos.presion_arterial or '---'}</font>", ParagraphStyle('value', fontSize=8, textColor=gris_medio)),
            Paragraph("<font size='7'>F. cardíaca:</font>", ParagraphStyle('label', fontSize=7, textColor=gris_claro)),
            Paragraph(f"<font size='8'>{signos.frecuencia_cardiaca or '---'} lpm</font>", ParagraphStyle('value', fontSize=8, textColor=gris_medio))
        ],
        [
            Paragraph("<font size='7'>F. respiratoria:</font>", ParagraphStyle('label', fontSize=7, textColor=gris_claro)),
            Paragraph(f"<font size='8'>{signos.frecuencia_respiratoria or '---'} rpm</font>", ParagraphStyle('value', fontSize=8, textColor=gris_medio)),
            Paragraph("<font size='7'>Sat. O₂:</font>", ParagraphStyle('label', fontSize=7, textColor=gris_claro)),
            Paragraph(f"<font size='8'>{signos.saturacion_oxigeno or '---'}%</font>", ParagraphStyle('value', fontSize=8, textColor=gris_medio)),
            Paragraph("<font size='7'>Peso:</font>", ParagraphStyle('label', fontSize=7, textColor=gris_claro)),
            Paragraph(f"<font size='8'>{signos.peso or '---'} kg</font>", ParagraphStyle('value', fontSize=8, textColor=gris_medio))
        ]
    ]
    
    signos_table = Table(signos_data, colWidths=[1.1*inch, 0.9*inch, 1.1*inch, 0.9*inch, 1.0*inch, 0.9*inch])
    signos_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 0), (-1, 0), 0.5, colors.lightgrey),
        ('LINEBELOW', (0, 1), (-1, 1), 0.5, colors.lightgrey),
    ]))
    
    elements.append(signos_table)
    elements.append(Spacer(1, 12))

    # ---------------------------------------
    # DIAGNÓSTICO (SI EXISTE)
    # ---------------------------------------
        # ---------------------------------------
    # DIAGNÓSTICO (SI EXISTE) - MISMO TAMAÑO QUE SIGNOS VITALES
    # ---------------------------------------
        # ---------------------------------------
    # DIAGNÓSTICO (SI EXISTE) - ANCHO 7.8 PULGADAS (COMO EN VERSIÓN ANTERIOR)
    # ---------------------------------------
    if cita.diagnostico and cita.diagnostico.strip():
        # Ajustar el espacio después de signos vitales
        if elements and isinstance(elements[-1], Spacer):
            elements[-1] = Spacer(1, 2)
        
        # Acortar diagnóstico
        diagnostico_texto = cita.diagnostico
        if len(diagnostico_texto) > 150:
            diagnostico_texto = diagnostico_texto[:147] + "..."
        
        # ANCHO IGUAL AL DE SIGNOS VITALES EN VERSIÓN ANTERIOR: 7.8 pulgadas
        diag_width = 7.8 * inch
        
        diag_data = [
            ['DIAGNÓSTICO'],
            [Paragraph(
                f"<font size='7'>{diagnostico_texto.replace(chr(10), '<br/>')}</font>", 
                ParagraphStyle('diagnostico', fontSize=7, textColor=gris_medio, leading=9, alignment=TA_CENTER)
            )]
        ]
        
        diag_table = Table(diag_data, colWidths=[diag_width], rowHeights=[0.25*inch, 0.6*inch])
        
        diag_table.setStyle(TableStyle([
            # Encabezado igual que signos vitales
            ('BACKGROUND', (0, 0), (-1, 0), azul_medio),
            ('TEXTCOLOR', (0, 0), (-1, 0), blanco),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('BOLD', (0, 0), (-1, 0), 1),
            ('TOPPADDING', (0, 0), (-1, 0), 4),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 4),
            
            # Contenido centrado
            ('ALIGN', (0, 1), (-1, 1), 'CENTER'),
            ('VALIGN', (0, 1), (-1, 1), 'MIDDLE'),
            ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#f5f5f5")),
            ('TOPPADDING', (0, 1), (-1, 1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, 1), 8),
            
            ('BOX', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ]))
        
        elements.append(diag_table)
        elements.append(Spacer(1, 6)) # Espacio similar al que sigue a signos vitales

    # ---------------------------------------
    # MEDICAMENTOS E INDICACIONES (MÁXIMO ESPACIO)
    # ---------------------------------------
    medicamentos_texto = (receta.medicamentos or "").replace("\n", "<br/>")
    indicaciones_texto = (receta.indicaciones or "").replace("\n", "<br/>")
    
    # Función para limitar texto
    def limitar_texto(texto, max_lineas=5):
        if not texto:
            return texto
        lineas = texto.split('<br/>')
        if len(lineas) <= max_lineas:
            return texto
        return '<br/>'.join(lineas[:max_lineas]) + "<br/>..."
    
    medicamentos_texto = limitar_texto(medicamentos_texto, 4)
    indicaciones_texto = limitar_texto(indicaciones_texto, 4)
    
    # Tabla pequeña de 2 columnas
        # Tabla de 2 columnas para medicamentos e indicaciones
    contenido_data = [
        [
            Paragraph("<font size='7'><b>MEDICAMENTOS PRESCRITOS</b></font>", 
                     ParagraphStyle('subtitulo', fontSize=7, textColor=blanco, alignment=TA_CENTER)),
            Paragraph("<font size='7'><b>INDICACIONES MÉDICAS</b></font>", 
                     ParagraphStyle('subtitulo', fontSize=7, textColor=blanco, alignment=TA_CENTER))
        ],
        [
            Paragraph(medicamentos_texto or "<i><font size='6' color='{gris_medio}'>Sin medicamentos</font></i>".format(gris_medio=gris_medio), 
                     ParagraphStyle('contenido', fontSize=6, textColor=gris_medio, leading=8, alignment=TA_JUSTIFY)),
            Paragraph(indicaciones_texto or "<i><font size='6' color='{gris_medio}'>Sin indicaciones</font></i>".format(gris_medio=gris_medio), 
                     ParagraphStyle('contenido', fontSize=6, textColor=gris_medio, leading=8, alignment=TA_JUSTIFY))
        ]
    ]
    
    # Altura pequeña para cuadros
    contenido_table = Table(contenido_data, colWidths=[3.4*inch, 3.4*inch], rowHeights=[0.3*inch, 1.0*inch])
    contenido_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (-1, 0), azul_medio),  # Fondo azul como signos vitales
        ('TEXTCOLOR', (0, 0), (-1, 0), blanco),  # Texto blanco como signos vitales
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, 0), 4),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 4),
        ('TOPPADDING', (0, 1), (-1, 1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, 1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
    ]))
    
    elements.append(contenido_table)
    elements.append(Spacer(1, 8))

    # ---------------------------------------
    # FIRMA
    # ---------------------------------------
    # Línea para firma
        # ---------------------------------------
    # FIRMA - SEPARADA DE LA TABLA ANTERIOR
    # ---------------------------------------
    # Agregar un Spacer para separar la firma de la tabla de arriba
    elements.append(Spacer(1, 10))  # Aumenta este valor para más separación
    
    # Línea para firma (más corta)
    linea_firma = Table([['']], colWidths=[2.0*inch], rowHeights=[0.3])
    linea_firma.setStyle(TableStyle([
        ('LINEABOVE', (0, 0), (-1, -1), 0.8, colors.black),
    ]))
    
    # Contenedor con todo alineado a la derecha
    firma_contenido = [
        [linea_firma],
        [Paragraph(
            f"<font size='7'><b>Dr. {doctor.user.get_full_name()}</b></font>", 
            ParagraphStyle("firma_nom", fontSize=7, alignment=TA_RIGHT)
        )],
        
    ]
    
    # Tabla que ocupa todo el ancho pero tiene contenido alineado a la derecha
    firma_table = Table(firma_contenido, colWidths=[7.4*inch])
    firma_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    
    elements.append(firma_table)
    elements.append(Spacer(1, 2))  # Pequeño espacio al final si es necesario

    # ---------------------------------------
    # CONSTRUIR DOCUMENTO
    # ---------------------------------------
    doc.build(elements)

    pdf = buffer.getvalue()
    buffer.close()

    response = HttpResponse(pdf, content_type="application/pdf")
    response['Content-Disposition'] = (
        f'attachment; filename="receta_medica_{paciente.nombre}_{cita.fecha.strftime("%Y%m%d")}.pdf"')
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