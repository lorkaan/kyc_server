from django.contrib import admin

from party.models import Party, PartyRelationship, PartyType

# Register your models here.
admin.site.register(PartyType)
admin.site.register(Party)
admin.site.register(PartyRelationship)