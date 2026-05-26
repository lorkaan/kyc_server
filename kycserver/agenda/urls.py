from rest_framework.routers import DefaultRouter
from django.urls import path
from .views import (
    AgendaEventTypeViewSet,
    AgendaEventViewSet,
    EventStatusListView
)

router = DefaultRouter()
router.register(r"event-types", AgendaEventTypeViewSet)
router.register(r"events", AgendaEventViewSet)

urlpatterns = router.urls + [path('event_status/', EventStatusListView.as_view(), name='event-status-list')]