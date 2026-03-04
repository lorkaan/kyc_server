from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser

from .models import (
    KYCRecord,
    KycAnswer,
    KycAnswerOption,
    PersonCompanyRelationship,
    ReferenceValue,
    RelationshipRole,
    KYCStatus,
    KycQuestion,
)
from .serializers import (
    KYCRecordSerializer,
    KycAnswerSerializer,
    KycAnswerOptionSerializer,
    PersonCompanyRelationshipSerializer,
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


# -------------------------------------------------
# KYC Answer Option ViewSet
# -------------------------------------------------
class KycAnswerOptionViewSet(ModelViewSet):
    queryset = KycAnswerOption.objects.all()
    serializer_class = KycAnswerOptionSerializer
    permission_classes = [IsAuthenticated]


# -------------------------------------------------
# PersonCompanyRelationship ViewSet
# -------------------------------------------------
class PersonCompanyRelationshipViewSet(ModelViewSet):
    queryset = PersonCompanyRelationship.objects.all()
    serializer_class = PersonCompanyRelationshipSerializer
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