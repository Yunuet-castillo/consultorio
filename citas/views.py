from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import IntegrityError
from .forms import ( RegistroForm, LoginForm, PacienteForm, CitaForm, SignosVitalesForm, RecetaForm, DiagnosticoForm)
from .models import CustomUser, Paciente, Cita, Doctor, SignosVitales, Receta
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

@login_required
@user_passes_test(is_administradora)
def dashboard_administradora(request):
    fecha_actual = date.today()
    # Filtramos citas cuyo día sea hoy o posterior
    citas = Cita.objects.filter(fecha__gte=fecha_actual).order_by('fecha', 'hora')
    contexto = {'citas': citas, 'fecha_actual': fecha_actual}
    return render(request, 'recepcion/dashboard.html', contexto)


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
    
    contexto = {'paciente_form': paciente_form}
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
    
    context = {'form': form, 'titulo': 'Agendar Cita', 'boton': 'Agendar', 'doctores': doctores}
    return render(request, 'recepcion/agendar_cita.html', context)

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
    cita = get_object_or_404(Cita, id=cita_id)
    signos = getattr(cita, 'signosvitales', None)
    receta = getattr(cita, 'receta', None)
    
    contexto = {
        "cita": cita,
        "paciente": cita.paciente,
        "signos": signos,
        "receta": receta
    }
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

    if request.method == "POST":
        form = RecetaForm(request.POST, instance=receta)
        if form.is_valid():
            nueva_receta = form.save(commit=False)
            nueva_receta.cita = cita
            nueva_receta.doctor = request.user.doctor  # ⚡ corregido
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
        "form": form
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
        messages.error(request, "No hay receta para esta cita.")
        return redirect('detalle_cita_doctor', cita_id=cita.id)

    paciente = cita.paciente
    doctor = cita.doctor
    signos = getattr(cita, 'signosvitales', None)

    # --- ✅ Cambiar el estado de la cita a “Atendida” ---
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

    # --- ✅ Al cerrar o imprimir, redirige al Dashboard ---
    dashboard_url = reverse('dashboard_doctor')

    # Si el navegador no muestra el PDF inline, fuerza redirección
    html_redirect = f"""
    <html>
        <body onload="window.open('data:application/pdf;base64,{pdf.decode('latin1')}', '_blank'); window.location.href='{dashboard_url}';">
            <p>Generando receta... redirigiendo al panel.</p>
        </body>
    </html>
    """

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="receta_{paciente.nombre}.pdf"'
    return response


@login_required
def detalle_paciente(request, paciente_id):
    paciente = get_object_or_404(Paciente, id=paciente_id)
    return render(request, 'recepcion/detalle_paciente.html', {'paciente': paciente})


@login_required
def buscar_pacientes(request):
    query = request.GET.get('q', '')
    pacientes = Paciente.objects.filter(nombre__icontains=query) if query else []
    return render(request, 'recepcion/buscar_pacientes.html', {
        'pacientes': pacientes,
        'query': query,
    })
# ---------------------------
# --- Reportes en PDF ---
# ---------------------------
import io
from django.http import FileResponse
from datetime import timedelta

def generar_pdf_reporte(titulo, citas):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer)
    styles = getSampleStyleSheet()
    story = [Paragraph(titulo, styles['Title']), Spacer(1, 12)]
    data = [["Paciente", "Doctor", "Fecha", "Estado"]]
    for c in citas:
        data.append([f"{c.paciente.nombre} {c.paciente.apellido}", c.doctor.user.get_full_name(), str(c.fecha), c.estado])
    story.append(Table(data))
    doc.build(story)
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename=f"{titulo}.pdf")

def reporte_dia(request):
    from .models import Cita
    hoy = date.today()
    citas = Cita.objects.filter(fecha=hoy, estado="Atendida")
    return generar_pdf_reporte(f"Reporte Diario - {hoy}", citas)

def reporte_semana(request):
    from .models import Cita
    hoy = date.today()
    inicio = hoy - timedelta(days=7)
    citas = Cita.objects.filter(fecha__range=[inicio, hoy], estado="Atendida")
    return generar_pdf_reporte(f"Reporte Semanal ({inicio} a {hoy})", citas)

def reporte_mes(request):
    from .models import Cita
    hoy = date.today()
    inicio = hoy.replace(day=1)
    citas = Cita.objects.filter(fecha__range=[inicio, hoy], estado="Atendida")
    return generar_pdf_reporte(f"Reporte Mensual ({inicio} a {hoy})", citas)

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
