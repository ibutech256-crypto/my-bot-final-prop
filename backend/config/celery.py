import os
from celery import Celery
os.environ.setdefault("DJANGO_SETTINGS_MODULE","backend.config.settings")
app=Celery("institutional_trading_platform"); app.config_from_object("django.conf:settings",namespace="CELERY"); app.autodiscover_tasks()
