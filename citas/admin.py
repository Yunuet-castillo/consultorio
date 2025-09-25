from django.contrib import admin
from .models import Paciente, Doctor, Cita, SignosVitales, Receta

# Para mostrar nombre completo en Paciente
class PacienteAdmin(admin.ModelAdmin):
    list_display = ('nombre_completo', 'fecha_nacimiento', 'telefono')

    def nombre_completo(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}"
    nombre_completo.short_description = 'Nombre'

admin.site.register(Paciente, PacienteAdmin)

class SignosVitalesAdmin(admin.ModelAdmin):
    list_display = ('cita', 'peso', 'presion_arterial', 'temperatura', 'frecuencia_cardiaca')

admin.site.register(SignosVitales, SignosVitalesAdmin)

admin.site.register(Doctor)
admin.site.register(Cita)
admin.site.register(Receta)
# Cambiar el título de la pestaña del navegado
admin.site.site_title = "Administración del Hospital San Pedro"

# Cambiar el encabezado grande en la parte superior
admin.site.site_header = "Sistema de Gestión Médica"

# Cambiar el título en la página principal del admin
admin.site.index_title = "Panel de control"

