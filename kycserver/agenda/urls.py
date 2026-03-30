from rest_framework.routers import DefaultRouter
from .views import (
    AgendaEventTypeViewSet,
    AgendaEventViewSet
)

router = DefaultRouter()
router.register(r"event-types", AgendaEventTypeViewSet)
router.register(r"events", AgendaEventViewSet)

urlpatterns = router.urls