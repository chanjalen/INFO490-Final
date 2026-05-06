"""
WSGI config for moviefinder project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os
import logging

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "moviefinder.settings")

application = get_wsgi_application()

try:
    from django.conf import settings
    from search.render_runtime import prepare_runtime_database

    if getattr(settings, "RUNNING_ON_RENDER", False):
        prepare_runtime_database(raise_errors=False)
except Exception:
    logging.getLogger(__name__).exception("WSGI Render preparation failed")
