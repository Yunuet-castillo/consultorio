from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, Paciente, Cita, SignosVitales, Receta,  Doctor
import datetime

# -------------------------
# Formulario de Login
# -------------------------
class LoginForm(forms.Form):
    username = forms.CharField(label="Usuario")
    role = forms.ChoiceField(choices=CustomUser.Roles.choices, label="Rol")
    role = forms.ChoiceField(
        choices=[('', '---Elige uno---')] + list(CustomUser.Roles.choices),
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
    role = forms.ChoiceField(choices=CustomUser.Roles.choices, label="Rol")
    email = forms.EmailField(label="Correo electrónico")

    username = forms.CharField(
        label="Usuario",
        max_length=150,
        help_text=None,      # Esto quita el texto de ayuda que dice los caracteres permitidos
        error_messages={     # Puedes dejar vacío o personalizar
            'required': 'Ingresa tu usuario.',
            'max_length': 'Máximo 150 caracteres.',
        }
    )
    
    role = forms.ChoiceField(
        choices=[('', '---Elige uno---')] + list(CustomUser.Roles.choices),
        label="Rol"
    )
    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ('username', 'nombre', 'apellido_paterno', 'apellido_materno', 'email', 'role',)

# -------------------------
# Formulario de Paciente
# -------------------------
from django import forms
from datetime import date
from .models import Paciente

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
        
        # Comprueba si la fecha de nacimiento es una fecha futura
        if fecha_nacimiento and fecha_nacimiento > date.today():
            raise forms.ValidationError("La fecha de nacimiento no puede ser una fecha futura.")
        
        return fecha_nacimiento

# -------------------------
# Formulario de Cita
# -------------------------
# En tu archivo citas/forms.py

from django import forms
from .models import Cita, Doctor  # Asegúrate de importar Doctor
from datetime import date

from django import forms
from .models import Cita, CustomUser  # Asegúrate de importar tu modelo de usuario
from datetime import date  # Importa la clase 'date'

class CitaForm(forms.ModelForm):
    
    # Campo 'doctor' definido explícitamente para el formulario.
    doctor = forms.ModelChoiceField(
        queryset=CustomUser.objects.filter(role=CustomUser.Roles.DOCTOR),
        label="Doctor",
        empty_label="Selecciona un doctor",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # La lógica de filtrado ya está en ModelChoiceField,
        # por lo que esta parte es redundante. Se puede dejar,
        # pero ya no es necesaria.
        # self.fields['doctor'].queryset = CustomUser.objects.filter(role=CustomUser.Roles.DOCTOR)
        pass

    class Meta:
        model = Cita
        fields = [
            'paciente', 
            'doctor',  # Asegúrate de que este campo esté aquí
            'fecha',
            'hora',
            # Si estos campos son requeridos, tu HTML también los necesita.
            'recordatorio_activado',
            'estado',
        ]
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date', 'min': date.today().isoformat()}),
            'hora': forms.TimeInput(attrs={'type': 'time'}),
        }
        
        from django import forms
from .models import Cita, CustomUser  # Asegúrate de importar tu modelo de usuario
from datetime import date  # Importa la clase 'date'

class CitaForm(forms.ModelForm):
    # Keep the queryset as is
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
    
    # Override the save method to handle the conversion
    def save(self, commit=True):
        # Get the CustomUser instance from the form
        doctor_user = self.cleaned_data.get('doctor_user')
        
        # Get the corresponding Doctor instance
        try:
            doctor_instance = Doctor.objects.get(user=doctor_user)
        except Doctor.DoesNotExist:
            raise forms.ValidationError("No Doctor instance found for the selected user.")

        # Create the Cita instance and assign the Doctor
        cita = super().save(commit=False)
        cita.doctor = doctor_instance

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
        fields = ['diagnostico', 'medicamentos', 'indicaciones']

# -------------------------
# Formulario de Cuestionario de Cita

# -------------------------
