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
def percent_to_price(arg1):
	return float(arg1) * 0.01

@register.filter
def usd_to_current(arg1):
	return float(arg1) * 0.1

@register.filter
def current_to_usd(arg1):
	return float(arg1) * 10

@register.filter
def mult(arg1, arg2):
	return float(arg1) * float(arg2)

@register.filter
def mult_three(arg1, arg2, arg3):
	return float(arg1) * float(arg2) * float(arg3)
