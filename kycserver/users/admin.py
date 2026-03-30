from django.contrib import admin

from users.forms import FieldPermissionsForm
from users.models import FieldPermissions, User

# Register your models here.
admin.site.register(User)

@admin.register(FieldPermissions)
class FieldPermissionsAdmin(admin.ModelAdmin):
    form = FieldPermissionsForm

    list_display = ("role", "model_name", "field_name", "get_flags")
    list_filter = ("role", "model_name")
    search_fields = ("model_name", "field_name")

    def get_flags(self, obj):
        flags = []
        if obj.has_flag(FieldPermissions.Flag.VIEW):
            flags.append("V")
        if obj.has_flag(FieldPermissions.Flag.EDIT):
            flags.append("E")
        if obj.has_flag(FieldPermissions.Flag.ADD):
            flags.append("A")
        if obj.has_flag(FieldPermissions.Flag.DELETE):
            flags.append("D")
        return "".join(flags)