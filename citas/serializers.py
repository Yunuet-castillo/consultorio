from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Cita, SignosVitales, Paciente  # ajusta según tus models

User = get_user_model()

# ==============================================================================
# 1. SERIALIZADOR DE REGISTRO
# ==============================================================================
class RegisterSerializer(serializers.ModelSerializer):
    password2 = serializers.CharField(write_only=True)
    class Meta:
        model = User
        fields = ('username','first_name','last_name','email','password','password2','rol')
        extra_kwargs = {'password': {'write_only': True}}

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError("Las contraseñas no coinciden")
        # opcional: validar rol = 'enfermera'
        if data.get('rol') != 'enfermera':
            raise serializers.ValidationError("El rol debe ser 'enfermera'")
        return data

    def create(self, validated_data):
        validated_data.pop('password2', None)
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

# ==============================================================================
# 2. SERIALIZADOR DE PACIENTE
# ==============================================================================
class PacienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Paciente 
        # Asegúrate de que los campos coincidan con tu models.py
        fields = ['id', 'nombre', 'apellido', 'edad', 'fecha_nacimiento', 'lugar_origen', 'telefono', 'primera_cita']


# ==============================================================================
# 3. SERIALIZADOR DE SIGNOS VITALES
#    (Debe ir ANTES de CitaSerializer)
# ==============================================================================
class SignosVitalesSerializer(serializers.ModelSerializer):
    # Para el POST (escritura)
    cita = serializers.PrimaryKeyRelatedField(queryset=Cita.objects.all()) 

    class Meta:
        model = SignosVitales
        # Lista exacta de campos que existen en el modelo
        fields = [
            'id', # Incluimos ID para lectura
            'cita',
            'peso',
            'presion_arterial',
            'temperatura',
            'frecuencia_cardiaca',
            'frecuencia_respiratoria',
            'saturacion_oxigeno'
        ]

# ==============================================================================
# 4. SERIALIZADOR DE CITA
# ==============================================================================
class CitaSerializer(serializers.ModelSerializer):
    # Anidación directa para la relación ForeignKey/OneToOne
    paciente = PacienteSerializer() 
    
    # Anidación para la relación inversa OneToOne (SignosVitales)
    signosvitales = serializers.SerializerMethodField()
    
    class Meta:
        model = Cita
        fields = ['id', 'fecha', 'hora', 'estado', 'paciente', 'signosvitales']

    # Función para manejar la serialización de la relación inversa
    def get_signosvitales(self, obj):
        # Acceder al objeto 'signosvitales' (nombre de relación inversa)
        # Importante: No usar self.context en el serializador anidado para la lectura
        signos_vitales_obj = getattr(obj, 'signosvitales', None)
        if signos_vitales_obj:
            # Usamos SignosVitalesSerializer para serializar el objeto
            return SignosVitalesSerializer(signos_vitales_obj).data
        return None