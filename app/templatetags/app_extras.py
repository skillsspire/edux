# app/templatetags/app_extras.py
from django import template

register = template.Library()

@register.filter
def get_item(d, key):
    """
    Безопасно получить d[key] в шаблоне:
    {{ my_dict|get_item:some_id }}
    """
    try:
        return d.get(key, 0)
    except Exception:
        return 0
