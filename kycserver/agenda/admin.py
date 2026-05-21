from django.contrib import admin

from .models import AgendaEvent, AgendaEventType

# Register your models here.
admin.site.register(AgendaEventType)
admin.site.register(AgendaEvent)