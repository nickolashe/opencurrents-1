from django import template

from datetime import date, datetime

import json
import logging
import pytz

from openCurrents.interfaces import convert

logging.basicConfig(level=logging.DEBUG, filename="log/views.log")
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

register = template.Library()

@register.filter
def subtract(val1, val2):
    return val1 - val2

@register.filter
def transform_stripe(val):
    return str(val).replace('.', '')

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
def datetime_cal(val, tz='UTC'):
    return val.astimezone(pytz.timezone(tz)).strftime('%Y-%m-%d %H:%M:%S')

@register.filter
def approve_date(val, tz='UTC'):
    strp_time = datetime.strptime(val, '%A, %m/%d')
    local_tz = pytz.timezone(tz)
    # return strp_time.astimezone(pytz.timezone(tz)).strftime('%A, %d/%m')
    return pytz.timezone(tz).localize(strp_time, is_dst=None).strftime('%A, %m/%d')

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
	return float(arg1) / float(convert._USDCUR)

@register.filter
def current_to_usd(arg1, arg2):
    res = float(arg1) * float(convert._USDCUR)

    if arg2 == 'with_fee':
        res *= (1 - convert._TR_FEE)

    return res

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

@register.filter
def jsonify_list_id(value):
    return json.dumps([value])

@register.filter('get_img_name_for_biz')
def get_img_name_for_biz(biz_name):
    if len(biz_name.split()) > 1:
        img_name = '-'.join(map(lambda s: s.lower(), biz_name.split()))
    else:
        img_name = biz_name.lower()

    return '/'.join([
        'img', '.'.join([img_name, 'png'])
    ])

@register.filter
def is_num(value):
    return isinstance(value, int)
