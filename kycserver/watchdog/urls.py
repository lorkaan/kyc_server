from django.urls import path, include
from rest_framework_nested import routers
from .views import AlertSeverityViewSet, AlertStatusViewSet, AlertViewSet


# Root router for main resources
router = routers.DefaultRouter()
router.register(r'alerts', AlertViewSet)
router.register(r'alert_status', AlertStatusViewSet)
router.register(r'alert_severity', AlertSeverityViewSet)

urlpatterns = router.urls