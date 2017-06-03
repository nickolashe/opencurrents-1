from django import template

import logging

logging.basicConfig(level=logging.DEBUG, filename="log/views.log")
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

register = template.Library()

@register.filter
def day(val):
    return val.strftime('%b %d, %Y')

@register.filter
def time(val):
    return val.strftime('%-I:%m %p')

@register.filter
def keyvalue(d, key):
    logger.info(key)
    return d[key]
