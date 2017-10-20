from django import template

import logging
import pytz

logging.basicConfig(level=logging.DEBUG, filename="log/views.log")
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

register = template.Library()

@register.filter
def day(val, tz='UTC'):
    return val.astimezone(pytz.timezone(tz)).strftime('%b %d, %Y')

@register.filter
def time(val, tz='UTC'):
    return val.astimezone(pytz.timezone(tz)).strftime('%-I:%M %p')

@register.filter
def keyvalue(d, key):
    return d[key]

@register.filter
def addstr(arg1, arg2):
    """concatenate arg1 & arg2"""
    return str(arg1) + str(arg2)

@register.filter
def percent_price(arg1, arg2):
	return format(float(arg1) * float(arg2), '.2f')
