import os, logging

logger= logging.getLogger("engine")

from django.core.wsgi import get_wsgi_application

# Override the DJANGO SETTINGS MODULE
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "conf.test.test_settings")

application = get_wsgi_application()

