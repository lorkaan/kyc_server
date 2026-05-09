from django.contrib import admin

from .forms import GlobalParameterAdminForm
from .models import GlobalParameter, StringValue


@admin.register(GlobalParameter)
class GlobalParameterAdmin(admin.ModelAdmin):
    form = GlobalParameterAdminForm

    list_display = ("name", "type", "is_active", "display_value")
    list_filter = ("type", "is_active")
    search_fields = ("name",)

    def display_value(self, obj):
        try:
            return obj.get_value()
        except Exception:
            return "⚠️ Invalid"
        
admin.site.register(StringValue)