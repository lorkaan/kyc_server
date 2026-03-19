from django.contrib import admin

from automation.models import AutomationAction, AutomationActionRun, AutomationRule, AutomationRun, AutomationTrigger

# Register your models here.
admin.site.register(AutomationRule)
admin.site.register(AutomationAction)
admin.site.register(AutomationTrigger)
admin.site.register(AutomationRun)
admin.site.register(AutomationActionRun)