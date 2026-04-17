from django.contrib import admin

from globalparams.models import BooleanValue, DateTimeValue, FloatValue, GlobalParameter, IntValue, StringValue, UUIDValue

# Register your models here.
admin.site.register(StringValue)
admin.site.register(IntValue)
admin.site.register(FloatValue)
admin.site.register(BooleanValue)
admin.site.register(UUIDValue)
admin.site.register(DateTimeValue)

class StringValueInline(admin.StackedInline):
    model = StringValue
    extra = 0
    max_num = 1

class IntValueInline(admin.StackedInline):
    model = IntValue
    extra = 0
    max_num = 1

class FloatValueInline(admin.StackedInline):
    model = FloatValue
    extra = 0
    max_num = 1

class BooleanValueInline(admin.StackedInline):
    model = BooleanValue
    extra = 0
    max_num = 1

class UUIDValueInline(admin.StackedInline):
    model = UUIDValue
    extra = 0
    max_num = 1

class DateTimeValueInline(admin.StackedInline):
    model = DateTimeValue
    extra = 0
    max_num = 1

@admin.register(GlobalParameter)
class GlobalParameterAdmin(admin.ModelAdmin):
    list_display = ("name", "type", "is_active", "get_value_display")
    readonly_fields = ("get_value_display",)

    def get_value_display(self, obj):
        return obj.get_value()
    
    def get_inline_instances(self, request, obj=None):
        if not obj:
            return []

        inline_map = {
            GlobalParameter.Type.STRING: StringValueInline,
            GlobalParameter.Type.INT: IntValueInline,
            GlobalParameter.Type.FLOAT: FloatValueInline,
            GlobalParameter.Type.BOOLEAN: BooleanValueInline,
            GlobalParameter.Type.UUID: UUIDValueInline,
            GlobalParameter.Type.DATETIME: DateTimeValueInline,
        }

        inline_class = inline_map.get(obj.type)
        if not inline_class:
            return []

        return [inline_class(self.model, self.admin_site)]