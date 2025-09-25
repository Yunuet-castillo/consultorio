from django import template

register = template.Library()

@register.filter(name='add_placeholder')
def add_placeholder(field, placeholder_text):
    """
    Permite agregar un placeholder a un campo de formulario en templates.
    Uso: {{ form.campo|add_placeholder:"Texto del placeholder" }}
    """
    return field.as_widget(attrs={"placeholder": placeholder_text, "class": "form-control"})
