from django.contrib import admin

from party.models import Party, PartyRelationship, PartyRelationshipCode, PartyRelationshipMetadata, PartyRelationshipMetadataCode, PartyType

# Register your models here.
admin.site.register(PartyType)
admin.site.register(Party)
admin.site.register(PartyRelationship)
admin.site.register(PartyRelationshipCode)
admin.site.register(PartyRelationshipMetadata)
admin.site.register(PartyRelationshipMetadataCode)