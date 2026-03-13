import datetime
import traceback

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
    KycBulkSubmitSerializer,
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
    
    def _validate_question_id(self, question_id, record_pk):
        if question_id == None:
            return False
        else:
            try:
                record_object = KYCRecord.objects.get(pk=record_pk)
                try:
                    kyc_question = KycQuestion.objects.get(pk=question_id)
                    if record_object.party != None and kyc_question.party_type == record_object.party.party_type:
                        return True
                    else:
                        return False
                except KycQuestion.DoesNotExist:
                    return False
                except Exception as e:
                    print(e)
                    return False
            except KycQuestion.DoesNotExist:
                return False
            except Exception as e:
                print(e)
                return False
    
    def _submit_single_answer(self, record_pk, item):
        question_id = question_id=item.get("question", None)
        if not self._validate_question_id(question_id, record_pk):
            raise Exception("Can not validate the Question/Record Pair")
        else:
            values = {
                "value_number": item.get("value_number"),
                "value_text": item.get("value_text"),
                "value_bool": item.get("value_bool"),
                "value_reference_id": item.get("value_reference"),

                "value_date": item.get("value_date"),
                "value_date_from": item.get("value_date_from"),
                "value_date_to": item.get("value_date_to"),

                "value_email": item.get("value_email"),
                "value_phone": item.get("value_phone"),
            }

            values = {k: v for k, v in values.items() if v is not None}
            options = item.get("selected_options", [])
            answer = KycAnswer(
                        kyc_record_id=record_pk,
                        question_id=question_id,
                        repeat_index=item.get("repeat_index", 0),
                        **values
                    )
            answer.save()
            for opt in options:
                try:
                    cur_ans_value = ReferenceValue.objects.get(pk=opt)
                    answer_option, created = KycAnswerOption.objects.get_or_create(answer=answer, reference_value=cur_ans_value)
                    if not created:
                        print(f"Answer Option already created: {answer_option}")
                except ReferenceValue.DoesNotExist as e:
                    print(f"Can not find the option: {opt}: {e}")
                    continue
                except Exception as e:
                    print(f"Unknown Error with AnswerOption: {e}")
                    continue
            return answer.id

    @transaction.atomic
    def bulk_add_answers(self, record_pk, answers_data):
        answer_ids = []
        for item in answers_data:
            answer_ids.append(self._submit_single_answer(record_pk, item))
        return answer_ids
    
    @action(detail=False, methods=["post"])
    def submit(self, request, record_pk=None, *args, **kwargs):

        try:

            payload = request.data
            answers_data = payload.get("answers", [])

            if not record_pk:
                return Response(
                    {"error": "record_pk missing in URL"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            answer_rows = self.bulk_add_answers(record_pk, answers_data)

            return Response({
                "status": "saved",
                "answers": answer_rows
            })

        except Exception:

            print("\n========== KYC SUBMIT ERROR ==========")
            print("URL record_pk:", record_pk)
            print("Payload:", request.data)
            traceback.print_exc()
            print("======================================\n")

            return Response(
                {"error": "internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
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