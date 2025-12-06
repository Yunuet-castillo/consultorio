from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, Paciente, Cita, SignosVitales, Receta, Doctor, Estudio
from datetime import date

# -------------------------
# Formulario de Login
# -------------------------
class LoginForm(forms.Form):
    username = forms.CharField(label="Usuario")
    role = forms.ChoiceField(label="Rol")
    password = forms.CharField(widget=forms.PasswordInput, label="Contraseña")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Excluir el rol "enfermera" de la lista
        roles = [r for r in CustomUser.Roles.choices if r[0] != "enfermera"]
        self.fields["role"].choices = [('', '---Elige tu rol---')] + roles


# -------------------------
# Formulario de Registro
# -------------------------
class RegistroForm(UserCreationForm):
    nombre = forms.CharField(label="Nombre")
    apellido_paterno = forms.CharField(label="Apellido Paterno")
    apellido_materno = forms.CharField(label="Apellido Materno", required=False)
    email = forms.EmailField(label="Correo electrónico")

    username = forms.CharField(
        label="Usuario",
        max_length=150,
        help_text=None,
        error_messages={
            'required': 'Ingresa tu usuario.',
            'max_length': 'Máximo 150 caracteres.',
        }
    )
    
    role = forms.ChoiceField(
        choices=[('', '---Elige tu rol---')] + list(CustomUser.Roles.choices),
        label="Rol"
    )

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ('username', 'nombre', 'apellido_paterno', 'apellido_materno', 'email', 'role',)

# -------------------------
# Formulario de Paciente
# -------------------------
from django import forms
from django.core.exceptions import ValidationError
from datetime import date
from .models import Paciente

class PacienteForm(forms.ModelForm):
    class Meta:
        model = Paciente
        fields = [
            'nombre',
            'apellido_paterno',
            'apellido_materno',
            'fecha_nacimiento',
            'edad',
            'lugar_origen',
            'telefono',
            'primera_cita'
        ]
        widgets = {
            'fecha_nacimiento': forms.DateInput(attrs={'type': 'date'}),
        }

    # Validación: fecha no puede ser futura
    def clean_fecha_nacimiento(self):
        fecha_nacimiento = self.cleaned_data.get('fecha_nacimiento')
        if fecha_nacimiento and fecha_nacimiento > date.today():
            raise forms.ValidationError("La fecha de nacimiento no puede ser una fecha futura.")
        return fecha_nacimiento

    # 🔥 Validación del teléfono (10 dígitos + no repetido)
    def clean_telefono(self):
        telefono = self.cleaned_data.get('telefono')

        if not telefono:
            raise ValidationError("Ingresa un número de teléfono.")

        # Validación: exactamente 10 dígitos
        if not telefono.isdigit() or len(telefono) != 10:
            raise ValidationError("El número debe tener exactamente 10 dígitos.")

        # Validación: evitar duplicados (pero permitir en edición)
        qs = Paciente.objects.filter(telefono=telefono)

        # Si se está editando un paciente, excluirlo de la validación
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise ValidationError("Este número de teléfono ya está registrado.")

        return telefono

# -------------------------
# Formulario de Cita
# -------------------------
from django.core.exceptions import ValidationError
from datetime import datetime, time, timedelta

class CitaForm(forms.ModelForm):
    doctor_user = forms.ModelChoiceField(
        queryset=Doctor.objects.all(),
        label="Doctor",
        empty_label="Selecciona un doctor",
    )

    class Meta:
        model = Cita
        fields = [
            'fecha',
            'hora',
            'recordatorio_activado',
           
        ]
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date', 'min': date.today().isoformat()}),
            'hora': forms.TimeInput(attrs={'type': 'time'}),
        }

    def __init__(self, *args, **kwargs):
        # recibir paciente automáticamente desde la vista
        self.paciente = kwargs.pop('paciente', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        fecha = cleaned_data.get('fecha')
        hora = cleaned_data.get('hora')
        doctor = cleaned_data.get('doctor_user')

        if not fecha or not hora or not doctor:
            return cleaned_data

        # Rango horario permitido: 9:30 AM a 4:00 PM
        hora_inicio = time(9, 30)
        hora_fin = time(16, 0)

        if not (hora_inicio <= hora <= hora_fin):
            raise ValidationError("⏰ Solo se pueden agendar citas entre 9:30 AM y 4:00 PM.")

        # Intervalo mínimo de 15 minutos
        citas_existentes = Cita.objects.filter(fecha=fecha, doctor=doctor)
        for cita in citas_existentes:
            diferencia = abs(datetime.combine(date.today(), cita.hora) - datetime.combine(date.today(), hora))
            if diferencia < timedelta(minutes=15):
                raise ValidationError(f"⚠️ Ya existe una cita para ese horario ({cita.hora.strftime('%H:%M')}). "
                                      "Debe dejar al menos 15 minutos de diferencia.")

        # Validar máximo de citas por día (ejemplo: 20 citas diarias por doctor)
        MAX_CITAS_POR_DIA = 20
        if citas_existentes.count() >= MAX_CITAS_POR_DIA:
            # Calcular horas disponibles
            horas_disponibles = []
            hora_actual = hora_inicio
            while hora_actual <= hora_fin:
                if not Cita.objects.filter(fecha=fecha, doctor=doctor, hora=hora_actual).exists():
                    horas_disponibles.append(hora_actual.strftime("%H:%M"))
                hora_actual = (datetime.combine(date.today(), hora_actual) + timedelta(minutes=15)).time()

            horas_str = ", ".join(horas_disponibles) if horas_disponibles else "Ninguna"
            raise ValidationError(
                f"📅 Este día ya tiene el máximo de citas asignadas. Por favor, seleccione otra fecha.\n"
                f"🕒 Horas disponibles: {horas_str}"
            )

        return cleaned_data

    def save(self, commit=True):
        doctor_user = self.cleaned_data.get('doctor_user')
        cita = super().save(commit=False)
        cita.doctor = doctor_user

        if self.paciente:
            cita.paciente = self.paciente  # asigna paciente automáticamente

        if commit:
            cita.save()
        return cita

# -------------------------
# Formulario de Signos Vitales
# -------------------------
class SignosVitalesForm(forms.ModelForm):
    class Meta:
        model = SignosVitales
        fields = [
            'peso',
            'presion_arterial',
            'temperatura',
            'frecuencia_cardiaca',
            'frecuencia_respiratoria',
            'saturacion_oxigeno'
        ]

# -------------------------
# Formulario de Receta
# -------------------------
class RecetaForm(forms.ModelForm):
    class Meta:
        model = Receta
        fields = ['medicamentos', 'indicaciones']
        widgets = {
            'medicamentos': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'indicaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

# -------------------------
# Formulario de Diagnóstico
# -------------------------
class DiagnosticoForm(forms.ModelForm):
    class Meta:
        model = Cita
        fields = ['diagnostico']
        widgets = {
            'diagnostico': forms.Textarea(attrs={'class': 'form-control', 'rows': 4})
        }




class EstudioForm(forms.ModelForm):
    class Meta:
        model = Estudio
        fields = ['archivo', 'descripcion']
        widgets = {
            'archivo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'descripcion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Descripción del estudio'}),
        }