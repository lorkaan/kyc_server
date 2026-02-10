from django.urls import include, path
from rest_framework import routers
from .views import SavedQueryViewSet

router = routers.DefaultRouter()
router.register("stored", SavedQueryViewSet)

urlpatterns = [
    path('', include(router.urls))
]
