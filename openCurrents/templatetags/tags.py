from django import template

import logging

register = template.Library()

@register.filter
def day(val):
    return val.strftime('%b %d, %Y')

@register.filter
def time(val):
    return val.strftime('%-I %p')
