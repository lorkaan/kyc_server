from django.contrib import admin

from .models import Alert, AlertReason, AlertSeverity, AlertStatus, Signal, SignalSeverity, SignalType

# Register your models here.
admin.site.register(AlertStatus)
admin.site.register(AlertReason)
admin.site.register(AlertSeverity)
admin.site.register(Alert)
admin.site.register(SignalType)
admin.site.register(SignalSeverity)
admin.site.register(Signal)