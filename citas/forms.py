from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, Paciente, Cita, SignosVitales, Receta, Doctor
from datetime import date

# -------------------------
# Formulario de Login
# -------------------------
class LoginForm(forms.Form):
    username = forms.CharField(label="Usuario")
    role = forms.ChoiceField(
        choices=[('', '---Elige tu rol---')] + list(CustomUser.Roles.choices),
        label="Rol"
    )
    password = forms.CharField(widget=forms.PasswordInput, label="Contraseña")

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
class PacienteForm(forms.ModelForm):
    class Meta:
        model = Paciente
        fields = [
            'nombre',
            'apellido',
            'edad',
            'fecha_nacimiento',
            'lugar_origen',
            'telefono',
            'primera_cita'
        ]
        widgets = {
            'fecha_nacimiento': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean_fecha_nacimiento(self):
        fecha_nacimiento = self.cleaned_data.get('fecha_nacimiento')
        if fecha_nacimiento and fecha_nacimiento > date.today():
            raise forms.ValidationError("La fecha de nacimiento no puede ser una fecha futura.")
        return fecha_nacimiento

# -------------------------
# Formulario de Cita
# -------------------------
class CitaForm(forms.ModelForm):
    doctor_user = forms.ModelChoiceField(
        queryset=Doctor.objects.all(),
        label="Doctor",
        empty_label="Selecciona un doctor",
    )

    class Meta:
        model = Cita
        fields = [
            'paciente', 
            'fecha',
            'hora',
            'recordatorio_activado',
            'estado',
        ]
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date', 'min': date.today().isoformat()}),
            'hora': forms.TimeInput(attrs={'type': 'time'}),
        }
    
    def save(self, commit=True):
        doctor_user = self.cleaned_data.get('doctor_user')
        cita = super().save(commit=False)
        cita.doctor = doctor_user  # asigna el modelo Doctor

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
        fields = ["diagnostico"]
        widgets = {
            "diagnostico": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }
