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
def day_only(val, tz='UTC'):
    return val.astimezone(pytz.timezone(tz)).strftime('%b %d')

@register.filter
def time(val, tz='UTC'):
    return val.astimezone(pytz.timezone(tz)).strftime('%-I:%M %p')

@register.filter
def keyvalue(d, key):
    return d[key]

@register.filter('get_value_from_dict')
def get_value_from_dict(dict_data, key):
    """
    usage example {{ your_dict|get_value_from_dict:your_key }}
    """
    if key:
        return dict_data.get(key)

@register.filter('subtract_time')
def subtract_time(value1, arg1):
    return round((value1 - arg1).total_seconds() / 3600,2)

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
def current_to_usd(arg1, arg2):
    if arg2 == 'with_fee':
        return float(arg1) * 9
    else:
		return float(arg1) * 10

@register.filter
def mult(arg1, arg2):
	return float(arg1) * float(arg2)

@register.filter
def mult_three(arg1, arg2, arg3):
	return float(arg1) * float(arg2) * float(arg3)

@register.filter
def str_to_num(arg1):
	return float(arg1)

@register.filter
def get_hours_total(arg1, arg2):
    return (arg2 - arg1).total_seconds() / 3600

@register.filter
def less(arg1, arg2):
    return arg1 - arg2

@register.filter
def fullname(firstname, lastname):
    return ' '.join([firstname, lastname])

@register.filter('round_number')
def round_number(value, decimals):
    s = "%."+ str(decimals) +"f"
    return s % round(value, decimals)
