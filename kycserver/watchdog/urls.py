from django.urls import path, include
from rest_framework_nested import routers
from .views import AlertViewSet


# Root router for main resources
router = routers.DefaultRouter()
router.register(r'alerts', AlertViewSet, basename='kyc-record')

urlpatterns = router.urls