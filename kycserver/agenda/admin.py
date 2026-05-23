from django.contrib import admin

from .models import AgendaEvent, AgendaEventType, AgendaEventTypeAlertSchedule

# Register your models here.
admin.site.register(AgendaEventType)
admin.site.register(AgendaEventTypeAlertSchedule)
admin.site.register(AgendaEvent)