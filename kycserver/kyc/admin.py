from django.contrib import admin

from .models import KYCRecord, KYCStatus, KycAnswer, KycAnswerOption, KycQuestion, ReferenceSet, ReferenceValue, RelationshipRole, RiskScore

# Register your models here.
admin.site.register(RelationshipRole)
admin.site.register(KYCStatus)
admin.site.register(KYCRecord)
admin.site.register(KycQuestion)
admin.site.register(KycAnswer)
admin.site.register(KycAnswerOption)
admin.site.register(ReferenceValue)
admin.site.register(ReferenceSet)
admin.site.register(RiskScore)
