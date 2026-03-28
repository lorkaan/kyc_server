# kyc/urls.py
from django.urls import path, include
from rest_framework_nested import routers
from .views import (
    KYCRecordViewSet,
    KycAnswerViewSet,
    KycAnswerOptionViewSet,
    RelationshipRoleViewSet,
    KYCStatusViewSet,
    KycQuestionViewSet,
    kyc_stream
)

# Root router for main resources
router = routers.DefaultRouter()
router.register(r'records', KYCRecordViewSet, basename='kyc-record')
router.register(r'answer-options', KycAnswerOptionViewSet, basename='kyc-answer-option')
router.register(r'roles', RelationshipRoleViewSet, basename='relationship-role')
router.register(r'statuses', KYCStatusViewSet, basename='kyc-status')
router.register(r'questions', KycQuestionViewSet, basename='kyc-question')

# Nested router for answers under records
records_router = routers.NestedDefaultRouter(router, r'records', lookup='record')
records_router.register(r'answers', KycAnswerViewSet, basename='kyc-record-answers')

urlpatterns = [
    path('', include(router.urls)),         # /records/, /questions/, /statuses/, etc.
    path('', include(records_router.urls)), # /records/<record_id>/answers/
    path('stream/', kyc_stream)
]