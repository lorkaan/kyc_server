from rest_framework.routers import DefaultRouter
from .views import (
    AgendaEventTypeViewSet,
    AgendaEventViewSet,
    EventStatusListView
)

router = DefaultRouter()
router.register(r"event-types", AgendaEventTypeViewSet)
router.register(r"events", AgendaEventViewSet)
router.register(r'event_status', EventStatusListView)

urlpatterns = router.urls