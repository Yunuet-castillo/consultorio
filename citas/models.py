from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import AbstractUser
from datetime import date
from rest_framework import serializers

# -------------------------
# Sección de Modelos de Usuario y Perfiles
# -------------------------

class CustomUser(AbstractUser):
    """
    Modelo de usuario extendido para incluir roles y datos personales básicos.
    """
    class Roles(models.TextChoices):
        ADMINISTRADORA = 'administradora', _('Administradora')
        ENFERMERA = 'enfermera', _('Enfermera')
        DOCTOR = 'doctor', _('Doctor')

    # Información personal
    nombre = models.CharField(_('nombre(s)'), max_length=100)
    apellido_paterno = models.CharField(_('apellido paterno'), max_length=100)
    apellido_materno = models.CharField(_('apellido materno'), max_length=150, blank=True, null=True)
    edad = models.IntegerField(_('edad'), null=True, blank=True)
    
    # Rol de usuario
    role = models.CharField(
        _('rol'),
        max_length=20,
        choices=Roles.choices
    )
    email = models.EmailField(_('email address'), unique=True)

    def __str__(self):
        return f"{self.username} - {self.role}"

    def get_full_name(self):
        """Devuelve el nombre completo del usuario."""
        return f"{self.nombre} {self.apellido_paterno} {self.apellido_materno or ''}".strip()

class Doctor(models.Model):
    """
    Modelo de perfil para doctores.
    """
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, primary_key=True)
    especialidad = models.CharField(max_length=100)
    cedula_profesional = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return f"Dr. {self.user.get_full_name()}"

class Paciente(models.Model):
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    edad = models.IntegerField(null=True, blank=True)
    fecha_nacimiento = models.DateField(default=date(1900, 1, 1))
    lugar_origen = models.CharField(max_length=100, blank=True, null=True)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    primera_cita = models.BooleanField(default=True)
    numero = models.CharField(max_length=10, unique=True, blank=True) # Campo numero para Paciente

    def save(self, *args, **kwargs):
        if not hasattr(self, 'numero') or not self.numero:
            last = Paciente.objects.all().order_by('id').last()
            if last:
                next_id = last.id + 1
            else:
                next_id = 1
            self.numero = f"P{next_id:04d}" # Ej: P0001, P0002, etc.
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nombre} {self.apellido}"


# -------------------------
# Sección de Modelos de Citas 
# -------------------------

class Cita(models.Model):
    ESTADO_CHOICES = (
        ('Pendiente', 'Pendiente'),
        ('Confirmada', 'Confirmada'),
        ('Cancelada', 'Cancelada'),
    )
    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE)
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE)
    fecha = models.DateField()
    hora = models.TimeField()
    recordatorio_activado = models.BooleanField(default=False)
    estado = models.CharField(max_length=50, choices=ESTADO_CHOICES, default='Pendiente')
    creada_en = models.DateTimeField(auto_now_add=True)
    # Aquí se eliminó la línea `numero = models.CharField(max_length=10, unique=True, blank=True)`

    def __str__(self):
        return f"Cita de {self.paciente} con {self.doctor} el {self.fecha} a las {self.hora}"

# -------------------------
# Sección de Modelos de Signos vitales 
# -------------------------
class SignosVitales(models.Model):
    """
    Modelo para registrar los signos vitales de una cita.
    """
    cita = models.OneToOneField(Cita, on_delete=models.CASCADE)
    peso = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    presion_arterial = models.CharField(max_length=20, null=True, blank=True)
    temperatura = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    frecuencia_cardiaca = models.IntegerField(null=True, blank=True)
    frecuencia_respiratoria = models.IntegerField(null=True, blank=True)
    saturacion_oxigeno = models.IntegerField(null=True, blank=True)
    
    class Meta:
        verbose_name_plural = "Signos Vitales"

    def __str__(self):
        return f"Signos vitales de {self.cita.paciente} - {self.cita.fecha}"



class SignosVitalesSerializer(serializers.ModelSerializer):
    class Meta:
        model = SignosVitales
        fields = '__all__'
        
class Receta(models.Model):
    """
    Modelo para emitir recetas médicas.
    """
    cita = models.ForeignKey(Cita, on_delete=models.CASCADE, related_name='recetas')
    diagnostico = models.TextField()
    medicamentos = models.TextField()
    indicaciones = models.TextField(blank=True, null=True)
    fecha_emision = models.DateField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Recetas"

    def __str__(self):
        return f"Receta para {self.cita.paciente} - {self.fecha_emision}"

    @property
    def paciente(self):
        return self.cita.paciente

    @property
    def doctor(self):
        return self.cita.doctor
    
    