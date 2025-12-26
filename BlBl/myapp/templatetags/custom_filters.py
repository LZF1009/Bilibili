from django import template
from openpyxl.styles.builtins import total

register = template.Library()
@register.filter
def split(value, delimiter):

    if value :
        return value.split(delimiter)
    return []

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def multiply(value, arg):
    try:
        return float(value)*float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def percenttage(value, arg):
    try:
        if total and float(value)  !=0:
            return round((float(value)) / float(total) * 100,1)
        return 0
    except (ValueError, TypeError):
        return 0

@register.filter
def format_number(value):
    try:
        num = float(value)
        if num >=10000:
            return f"{num/10000:1f}w"
        elif num >=1000:
            return f"{num/1000:1f}k"
        else:
            return str(int(num))
    except (ValueError, TypeError):
        return value