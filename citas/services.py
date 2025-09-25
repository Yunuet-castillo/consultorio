from datetime import date
from .models import Cita

def reagendar_siguiente_disponible(cita: Cita):
    if cita.estado != 'cancelada':
        return None
    # buscar en el mismo día
    hora_libre = Cita.siguiente_espacio_disponible(cita.fecha)
    if hora_libre:
        cita.hora = hora_libre
        cita.estado = 'programada'
        cita.save()
        return cita

    # si no hay el mismo día, busca los próximos 14 días
    for i in range(1, 15):
        nueva_fecha = cita.fecha + timedelta(days=i)
        hora_libre = Cita.siguiente_espacio_disponible(nueva_fecha)
        if hora_libre:
            cita.fecha = nueva_fecha
            cita.hora = hora_libre
            cita.estado = 'programada'
            cita.save()
            return cita
    return None
