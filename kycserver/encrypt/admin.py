from django.contrib import admin

from encrypt.models import EncryptionType, EncryptionValue

# Register your models here.
admin.site.register(EncryptionType)
admin.site.register(EncryptionValue)