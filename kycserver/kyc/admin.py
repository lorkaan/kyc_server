from django.contrib import admin

from .models import KYCRecord, KYCStatus, KycAnswer, KycAnswerOption, KycQuestion, KycQuestionOption, PersonCompanyRelationship, RelationshipRole

# Register your models here.
admin.site.register(RelationshipRole)
admin.site.register(PersonCompanyRelationship)
admin.site.register(KYCStatus)
admin.site.register(KYCRecord)
admin.site.register(KycQuestion)
admin.site.register(KycQuestionOption)
admin.site.register(KycAnswer)
admin.site.register(KycAnswerOption)