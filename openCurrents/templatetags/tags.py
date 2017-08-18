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
    logger.info(key)
    return d[key]