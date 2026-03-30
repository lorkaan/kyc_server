from django.contrib import admin

from users.forms import FieldPermissionsForm, UserAdminForm
from users.models import FieldPermissions, User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

# Register your models here.
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = UserAdminForm
    list_display = ('username', 'email', 'role', 'is_staff', 'is_superuser')
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('full_name', 'email')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('date_joined',)}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}
        ),
    )
    search_fields = ('username', 'email')
    ordering = ('username',)
    filter_horizontal = ('groups', 'user_permissions')  # <-- two-box style


#@admin.register(FieldPermissions)
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