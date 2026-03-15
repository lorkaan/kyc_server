from django.contrib import admin

from automation.models import AutomationAction, AutomationRule

# Register your models here.
admin.site.register(AutomationRule)
admin.site.register(AutomationAction)