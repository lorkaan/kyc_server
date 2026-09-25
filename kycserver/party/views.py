from django.shortcuts import render
from base.views import BaseViewSet
from kyc.models import KYCRecord
from kyc.serializers import KYCRecordSerializer
from utils.dict_utils import dictToStr
from rest_framework import viewsets, mixins, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Q
from django.db import transaction
from rest_framework.permissions import IsAuthenticated

from .models import PartyRelationshipCode, PartyRelationshipMetadata, PartyType, Party, PartyRelationship
from .serializers import (
    PartyGraphSerializer,
    PartyRelationshipCodeSerializer,
    PartyRelationshipMetadataSerializer,
    PartyRelationshipMetadataWriteSerializer,
    PartyRelationshipReadSerializer,
    PartyRelationshipUpdateSerializer,
    PartyTypeSerializer,
    PartySerializer,
    PartyRelationshipSerializer,
    PartyCreateSerializer,
)

# Create your views here.
class PartyTypeViewSet(BaseViewSet):
    queryset = PartyType.objects.all()
    serializer_class = PartyTypeSerializer
    lookup_field = "code"

    def get_queryset(self):
        queryset = super().get_queryset()

        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == "true")

        return queryset
    
    @action(detail=True, methods=["get"])
    def schema(self, request, code=None):
        party_type = self.get_object()
        Serializer = party_type.get_serializer()

        serializer = Serializer()
        fields = serializer.get_fields()

        schema = {}

        for name, field in fields.items():
            schema[name] = {
                "type": field.__class__.__name__,
                "required": field.required,
                "read_only": field.read_only,
            }

        return Response(schema)
    
class PartyViewSet(BaseViewSet):
    queryset = Party.objects.select_related("party_type", "content_type")
    serializer_class = PartySerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        party_type = self.request.query_params.get("party_type")
        name = self.request.query_params.get("name")
        is_active = self.request.query_params.get("is_active")

        if party_type:
            queryset = queryset.filter(party_type__code=party_type)

        if name:
            queryset = queryset.filter(name__icontains=name)

        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == "true")

        return queryset

    def get_serializer_class(self):
        if self.action == "create":
            return PartyCreateSerializer
        return PartySerializer

    def create(self, request, *args, **kwargs):
        """
        Override to return full PartySerializer after creation
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        party = serializer.save()

        output_serializer = PartySerializer(party, context={"request": request})
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def relationships(self, request, pk=None):
        """
        Get relationships where this party is involved
        """
        party = self.get_object()

        relationships = PartyRelationship.objects.filter(
            Q(party=party) | Q(target_party=party)
        ).select_related("party", "target_party", "role")

        serializer = PartyRelationshipSerializer(relationships, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=["post"])
    def edit(self, request, pk=None):
        record = self.get_object()
        data = request.data.get("party")
        party_id = data.get('id', None)
        if party_id != None and str(record.id).strip() == str(party_id).strip():
            record.name = data.get('name')
            entity = record.content_object
            entity_data = request.data.get("entity")

            if entity and entity_data:
                serializer_class = record.party_type.get_serializer()

                serializer = serializer_class(
                    entity,
                    data=entity_data,
                    partial=True
                )
                serializer.is_valid(raise_exception=True)
                serializer.save()
            record.save()
            return Response({"update": True})
        else:
            import logging
            logger = logging.getLogger()
            logger.error(f"Party ID: {type(party_id)} -> {type(record.id)}")
            return Response(status=status.HTTP_400_BAD_REQUEST)
        
    @action(detail=True, methods=["get"])
    def kyc(self, request, pk=None):
        party = self.get_object()
        record = KYCRecord.objects.filter(party=party).order_by("-created_at").first()
        if record is None:
            return Response(
                {"detail": "No KYC record found for this party"},
                status=status.HTTP_404_NOT_FOUND
            )
        else:
            output_serializer = KYCRecordSerializer(record)
            return Response(output_serializer.data, status=status.HTTP_201_CREATED)
    
class PartyRelationshipViewSet(BaseViewSet):
    queryset = PartyRelationship.objects.select_related(
        "party",
        "target_party",
        "role"
    )
    serializer_class = PartyRelationshipReadSerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        party = self.request.query_params.get("party")
        target_party = self.request.query_params.get("target_party")
        role = self.request.query_params.get("role")

        if party:
            queryset = queryset.filter(party_id=party)

        if target_party:
            queryset = queryset.filter(target_party_id=target_party)

        if role:
            queryset = queryset.filter(role_id=role)

        return queryset
    
# views.py
import logging
class PartyGraphViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    logger = logging.getLogger()

    @action(detail=False, methods=["post"], url_path="create-graph")
    def create_graph(self, request):
        self.logger.error("Creating Graph Start")

        serializer = PartyGraphSerializer(data=request.data)
        if not serializer.is_valid():
            self.logger.error(f"Validation errors: {serializer.errors}")
            return Response(serializer.errors, status=400)

        result = serializer.save()  # 🔥 ALL logic happens inside serializer

        return Response({
            "main_party_id": result["party"].id,
            "relationships_created": [
                rel.id for rel in result["relationships"]
            ]
        }, status=status.HTTP_201_CREATED)

class PartyRelationshipUpdateViewSet(
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = PartyRelationship.objects.all()
    serializer_class = PartyRelationshipUpdateSerializer

    http_method_names = ["patch"]

class PartyRelationshipMetadataReadViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PartyRelationshipMetadataSerializer
    permission_classes = [IsAuthenticated]  # optional

    def get_queryset(self):
        """
        Optimized queryset with optional filtering by relationship.
        """
        queryset = (
            PartyRelationshipMetadata.objects
            .select_related("relationship")
            .prefetch_related("codes__code")  # metadata -> codes -> code
        )

        relationship_id = self.request.query_params.get("relationship")

        if relationship_id:
            queryset = queryset.filter(relationship_id=relationship_id)

        return queryset

class PartyRelationshipMetadataWriteViewSet(viewsets.ModelViewSet):
    serializer_class = PartyRelationshipMetadataWriteSerializer
    queryset = PartyRelationshipMetadata.objects.all()

    # Only allow write operations
    http_method_names = ["post", "put", "patch", "delete"]

    def get_queryset(self):
        """
        Optional: allow filtering by relationship
        """
        queryset = super().get_queryset()

        relationship_id = self.request.query_params.get("relationship")
        if relationship_id:
            queryset = queryset.filter(relationship_id=relationship_id)

        return queryset

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        Create metadata + associated codes
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()

        return Response(
            self.get_serializer(instance).data,
            status=status.HTTP_201_CREATED
        )

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """
        Full update (PUT)
        """
        partial = kwargs.pop("partial", False)
        instance = self.get_object()

        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=partial
        )
        serializer.is_valid(raise_exception=True)

        # Optional: prevent relationship changes
        if "relationship" in serializer.validated_data:
            serializer.validated_data.pop("relationship")

        instance = serializer.save()

        return Response(self.get_serializer(instance).data)

    @transaction.atomic
    def partial_update(self, request, *args, **kwargs):
        """
        Partial update (PATCH)
        """
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """
        Delete metadata (and cascade delete codes)
        """
        instance = self.get_object()
        instance.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)

class PartyRelationshipCodeViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PartyRelationshipCodeSerializer

    def get_queryset(self):
        return PartyRelationshipCode.objects.all().order_by("code")