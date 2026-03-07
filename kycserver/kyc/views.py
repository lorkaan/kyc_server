from person.models import Person
from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser
from rest_framework import status
from django.db import transaction
from django.contrib.contenttypes.models import ContentType

from .models import (
    KYCRecord,
    KycAnswer,
    KycAnswerOption,
    ReferenceValue,
    RelationshipRole,
    KYCStatus,
    KycQuestion,
)
from .serializers import (
    KYCRecordSerializer,
    KycAnswerSerializer,
    KycAnswerOptionSerializer,
    RelationshipRoleSerializer,
    KYCStatusSerializer,
)
from base.serializers import HistoryEventSerializer  # If you have pghistory events

# -------------------------------------------------
# KYC Record ViewSet
# -------------------------------------------------
class KYCRecordViewSet(ModelViewSet):
    queryset = KYCRecord.objects.all()
    serializer_class = KYCRecordSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        """
        Return pghistory events for a record.
        """
        record = self.get_object()
        events = record.pghistory_events.all().order_by("-pgh_created_at")
        serializer = HistoryEventSerializer(events, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def questions(self, request):
        """
        Return all KYC questions grouped by their group.
        Useful for frontend wizard.
        """
        from .models import KycQuestionGroup

        groups = KycQuestionGroup.objects.prefetch_related(
            "questions",
            "questions__reference_set",
            "questions__reference_set__values",
            "questions__conditions"
        ).order_by("order")

        data = []
        for g in groups:
            group_data = {
                "id": g.id,
                "key": g.key,
                "label": g.label,
                "order": g.order,
                "is_repeatable": g.is_repeatable,
                "questions": []
            }
            for q in g.questions.all().order_by("order"):
                question_data = {
                    "id": q.id,
                    "key": q.key,
                    "label": q.label,
                    "answer_type": q.answer_type,
                    "required": q.required,
                    "is_repeatable": q.is_repeatable,
                    "reference_set": {
                        "id": q.reference_set.id,
                        "key": q.reference_set.key,
                        "name": q.reference_set.name,
                        "values": [
                            {
                                "id": v.id,
                                "code": v.code,
                                "label": v.label
                            } for v in getattr(q.reference_set, "values", []).all()
                        ]
                    } if q.reference_set else None,
                    "conditions": [
                        {
                            "id": c.id,
                            "type": c.condition_type,
                            "rule": c.rule
                        } for c in q.conditions.all()
                    ]
                }
                group_data["questions"].append(question_data)
            data.append(group_data)

        return Response(data)
    
    @action(detail=False, methods=["post"])
    @transaction.atomic
    def start(self, request):
        """
        Start a KYC session for any PartyType (Person, Company, etc.)
        """

        party_type_code = request.data.get("party_type")
        entity_id = request.data.get("entity_id")
        entity_data = request.data.get("entity_data")

        if not party_type_code:
            return Response(
                {"error": "party_type is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        from kyc.models import PartyType, Party, KYCRecord, KYCStatus

        # Fetch PartyType
        try:
            party_type = PartyType.objects.get(code=party_type_code)
        except PartyType.DoesNotExist:
            return Response(
                {"error": f"Invalid party_type '{party_type_code}'"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Step 1: Fetch or create the underlying entity via create_entity()
        if entity_id:
            content_model = party_type.get_serializer().Meta.model
            entity = content_model.objects.get(id=entity_id)
        elif entity_data:
            entity = party_type.create_entity(entity_data)  # <- Use create_entity here
        else:
            return Response(
                {"error": "entity_id or entity_data required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Step 2: Get or create the Party
        content_type = ContentType.objects.get_for_model(entity)
        party, created = Party.objects.get_or_create(
            party_type=party_type,
            content_type=content_type,
            object_id=entity.pk,
            defaults={"display_name": str(entity)}
        )

        # Step 3: Get or create KYCRecord for this Party
        record, created = KYCRecord.objects.get_or_create(
            party=party,
            defaults={
                "status": KYCStatus.objects.get(code="pending"),
                "risk_score": 0
            }
        )

        return Response({
            "party_id": party.id,
            "kyc_record_id": record.id
        })

# -------------------------------------------------
# KYC Answer ViewSet
# -------------------------------------------------
class KycAnswerViewSet(ModelViewSet):
    queryset = KycAnswer.objects.all()
    serializer_class = KycAnswerSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=["post"], parser_classes=[MultiPartParser])
    def upload(self, request, pk=None):
        """
        Upload supporting document for answer
        """
        answer = self.get_object()
        file = request.FILES.get("file")

        if not file:
            return Response({"error": "No file uploaded"}, status=400)

        from .models import KycAnswerAttachment
        attachment = KycAnswerAttachment.objects.create(
            answer=answer,
            file=file,
            original_name=file.name,
            content_type=file.content_type,
            size=file.size,
            uploaded_by=request.user
        )

        return Response({
            "id": attachment.id,
            "name": attachment.original_name
        })
    
    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        """Submit multiple answers for a KYC record"""
        kyc_record = self.get_object()
        answers_data = request.data.get("answers", [])
        serializer = self.get_serializer(data=answers_data, many=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(kyc_record=kyc_record)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# -------------------------------------------------
# KYC Answer Option ViewSet
# -------------------------------------------------
class KycAnswerOptionViewSet(ModelViewSet):
    queryset = KycAnswerOption.objects.all()
    serializer_class = KycAnswerOptionSerializer
    permission_classes = [IsAuthenticated]



# -------------------------------------------------
# RelationshipRole ViewSet
# -------------------------------------------------
class RelationshipRoleViewSet(ModelViewSet):
    queryset = RelationshipRole.objects.all()
    serializer_class = RelationshipRoleSerializer
    permission_classes = [IsAuthenticated]


# -------------------------------------------------
# KYCStatus ViewSet
# -------------------------------------------------
class KYCStatusViewSet(ModelViewSet):
    queryset = KYCStatus.objects.all()
    serializer_class = KYCStatusSerializer
    permission_classes = [IsAuthenticated]


# -------------------------------------------------
# KycQuestion ViewSet (optional)
# -------------------------------------------------
class KycQuestionViewSet(ModelViewSet):
    queryset = KycQuestion.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        # Use simple serializer for frontend question loading
        class QuestionSerializer(serializers.ModelSerializer):
            class Meta:
                model = KycQuestion
                fields = [
                    "id", "key", "label", "answer_type", "required",
                    "is_repeatable", "reference_set", "group"
                ]
        return QuestionSerializer