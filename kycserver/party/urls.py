from rest_framework.routers import DefaultRouter
from .views import (
    PartyGraphViewSet,
    PartyTypeViewSet,
    PartyViewSet,
    PartyRelationshipViewSet
)

router = DefaultRouter()
router.register(r"party-types", PartyTypeViewSet)
router.register(r"parties", PartyViewSet)
router.register(r"relationships", PartyRelationshipViewSet)
router.register(r"party-graph", PartyGraphViewSet)

urlpatterns = router.urls