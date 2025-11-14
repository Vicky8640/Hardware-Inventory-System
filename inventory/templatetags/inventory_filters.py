from django import template

register = template.Library()

@register.filter
def mul(value, arg):
    """Multiplies the argument with the value."""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return ''