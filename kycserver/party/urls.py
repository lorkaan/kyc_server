from rest_framework.routers import DefaultRouter
from .views import (
    PartyGraphViewSet,
    PartyRelationshipMetadataReadViewSet,
    PartyRelationshipMetadataWriteViewSet,
    PartyRelationshipUpdateViewSet,
    PartyTypeViewSet,
    PartyViewSet,
    PartyRelationshipViewSet
)

router = DefaultRouter()
router.register(r"party-types", PartyTypeViewSet)
router.register(r"parties", PartyViewSet)
router.register(r"relationships", PartyRelationshipViewSet)
router.register(r'relationship-update', PartyRelationshipUpdateViewSet, basename="relationship-update")
router.register(r"party-graph", PartyGraphViewSet, basename="party-graph")
router.register(r"relationship-metadata", PartyRelationshipMetadataReadViewSet, basename="relationship-metadata-read")
router.register(r"relationship-metadata-write", PartyRelationshipMetadataWriteViewSet, basename="relationship-metadata-write")


urlpatterns = router.urls