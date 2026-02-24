from celery import Celery
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kycserver.settings")

import django
django.setup() 

app = Celery("kycserver")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
