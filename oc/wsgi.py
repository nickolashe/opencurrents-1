"""
WSGI config for oc project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.10/howto/deployment/wsgi/
"""

import os, sys

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "oc.settings")

try:
    application = get_wsgi_application()
    print 'WSGI without exception'
except Exception as e:
    print 'handling WSGI exception'
    print e.message
    # Error loading applications
    if 'mod_wsgi' in sys.modules:
        traceback.print_exc()
        os.kill(os.getpid(), signal.SIGINT)
        time.sleep(2.5)

# application = get_wsgi_application()
