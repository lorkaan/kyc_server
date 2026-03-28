import datetime
import traceback

from kyc.handlers import ANSWER_HANDLERS
from party.models import PartyType
from person.models import Person
from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action, renderer_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser
from rest_framework import status
from django.db import transaction
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
import redis
from django.conf import settings
from django.http import StreamingHttpResponse
import json
import logging
from .models import KycQuestionGroup
from django.db.models import Prefetch


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
    KycQuestionSerializer,
    RelationshipRoleSerializer,
    KYCStatusSerializer,
)
from base.serializers import HistoryEventSerializer  # If you have pghistory events
from rest_framework.renderers import BaseRenderer


class EventStreamRenderer(BaseRenderer):
    media_type = 'text/event-stream'
    format = None
    charset = 'utf-8'

    def render(self, data, media_type=None, renderer_context=None):
        return data  # Already bytes or string


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

    @action(detail=False, methods=["post"])
    def questions(self, request):
        """
        Return all KYC questions grouped by their group.
        Useful for frontend wizard.
        """

        party_type_id = request.data.get("party_type_id")
        if type(party_type_id) == str:
            try:
                party_type_id = int(party_type_id)
            except Exception as e:
                return Response(
                    {"error": e},
                    status=status.HTTP_400_BAD_REQUEST
                )
        try:
            party_type = PartyType.objects.get(pk=party_type_id)
        except PartyType.DoesNotExist as e:
            return Response(
                {"error": e},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            return Response(
                {"error": e},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        question_qs = KycQuestion.objects.filter(
            party_type=party_type
        ).select_related(
            "reference_set"
        ).prefetch_related(
            "reference_set__values",
            "conditions"
        ).order_by("order")

        # Prefetch ONLY filtered questions into groups
        groups = KycQuestionGroup.objects.prefetch_related(
            Prefetch("questions", queryset=question_qs)
        ).order_by("order")

        '''
        groups = KycQuestionGroup.objects.prefetch_related(
            "questions",
            "questions__reference_set",
            "questions__reference_set__values",
            "questions__conditions"
        ).order_by("order")
        '''

        data = []

        for g in groups:
            questions = list(g.questions.all())

            # Skip empty groups (important)
            if not questions:
                continue

            group_data = {
                "id": g.id,
                "key": g.key,
                "label": g.label,
                "order": g.order,
                "is_repeatable": g.is_repeatable,
                "questions": []
            }

            for q in questions:
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
            defaults={"name": str(entity)}
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

    @action(detail=False, methods=["post"])
    def party_info(self, request):
        """
        Given a KYCRecord UUID, return the Party and its PartyType
        """

        record_id = request.data.get("kyc_record_id")

        if not record_id:
            return Response(
                {"error": "kyc_record_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            record = KYCRecord.objects.select_related("party__party_type").get(id=record_id)
        except KYCRecord.DoesNotExist:
            return Response(
                {"error": "KYCRecord not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        party = record.party
        party_type = party.party_type

        return Response({
            "party": {
                "id": party.id,
                "name": party.name,
            },
            "party_type": {
                "id": party_type.id,
                "code": party_type.code,
                "name": getattr(party_type, "name", None),
            }
        })
    
    @action(detail=False, methods=["get"], renderer_classes=[])
    #@renderer_classes([EventStreamRenderer])
    def stream(self, request):
        """
        SSE endpoint for streaming KYCRecords for the logged-in user.
        Sends:
          - Existing pending/in-progress KYCRecords immediately
          - Any new KYCRecord events via Redis pub/sub
        """
        #user = request.user
        #user_id = user.id
        request.accepted_renderer = None
        request.accepted_media_type = "text/event-stream"

        def event_stream():
            # 1️⃣ Send existing KYCRecords
            existing = KYCRecord.objects.filter(
                status__code__in=["created", "pending", "in_progress", "requires_update", "expired"]
            )
            for record in existing:
                yield sse_event({
                    "id": record.id,
                    "party_id": record.party_id,
                    "status": record.status.code,
                    "created_at": record.created_at.isoformat(),
                }, event="kyc_record_init")

            # 2️⃣ Subscribe to Redis channel for new KYCRecords
            pubsub = redis_client.pubsub(ignore_subscribe_messages=True)
            pubsub.subscribe(f"kyc_records")  # user-specific channel

            try:
                for message in pubsub.listen():
                    if message["type"] != "message":
                        continue
                    data = json.loads(message["data"])
                    yield sse_event(data, event="kyc_record_new")
            finally:
                pubsub.close()

        response = StreamingHttpResponse(
            event_stream(),
            content_type="text/event-stream"
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"  # for nginx to flush
        return response

# -------------------------------------------------
# KYC Answer ViewSet
# -------------------------------------------------
class KycAnswerViewSet(ModelViewSet):

    logger = logging.getLogger()

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
    
    def _validate_question(self, question, record):
        """
        Accepts either PKs or model instances for both inputs.
        Returns True/False.
        """

        try:
            # Resolve record
            if isinstance(record, KYCRecord):
                record_obj = record
            else:
                record_obj = KYCRecord.objects.get(pk=record)

            # Resolve question
            if isinstance(question, KycQuestion):
                question_obj = question
            else:
                question_obj = KycQuestion.objects.get(pk=question)

        except (KYCRecord.DoesNotExist, KycQuestion.DoesNotExist):
            return False, None, None
        except Exception as e:
            print(e)
            return False, None, None

        # -----------------------
        # Business logic
        # -----------------------

        if not record_obj.party:
            return False, record_obj, question_obj

        return question_obj.party_type == record_obj.party.party_type, record_obj, question_obj
            
    def create_kyc_answer(self, *, kyc_record, question, value, repeat_index=0):
        validation, kyc_record_obj, question_obj = self._validate_question(question, kyc_record)
        if not validation:
            raise ValidationError(f"Can not validate that this KYC Question: {question} works with the KycRecord: {kyc_record}")

        answer = KycAnswer(
            kyc_record=kyc_record_obj,
            question=question_obj,
            repeat_index=repeat_index,
        )

        handler = ANSWER_HANDLERS.get(question_obj.answer_type)

        if not handler or not callable(handler):
            raise ValidationError(f"Unsupported answer type: \n\tQuestion: {question}\n\tType: {question_obj.answer_type}\n\tValue Type: {type(value)}\n\tValue: {value}")

        # Note: Do not need transaction.atomic here because this is wrapped in one.

        # Apply handler
        handler(answer, value, question_obj)

        # Run full validation (important!)
        answer.full_clean()

        # Save if not already saved (MULTI handler saves early)
        if not answer.pk:
            answer.save()

        return answer
    
    def _submit_single_answer(self, record_pk, item):
        """
            Depreciated
        """
        question_id = item.get("question", None)
        if not self._validate_question_id(question_id, record_pk):
            raise Exception(f"Can not validate the Question/Record Pair: \n\tRecord: {record_pk}\n\tQuestion: {question_id}")
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
        try:
            kyc_record = KYCRecord.objects.get(pk=record_pk)
            for item in answers_data:
                question = item["question"]
                repeat_index = item.get("repeat_index", 0)

                # Determine value explicitly
                if "selected_options" in item:
                    value = item["selected_options"]
                elif "value_date_from" in item or "value_date_to" in item:
                    value = {"from": item.get("value_date_from"), "to": item.get("value_date_to")}
                else:
                    # pick the first value_* key (simplest)
                    value_keys = [
                        "value_number", "value_text", "value_bool",
                        "value_reference", "value_date", "value_email", "value_phone"
                    ]
                    value = next((item[k] for k in value_keys if k in item), None)
                answer_ids.append(self.create_kyc_answer(kyc_record=kyc_record, question=question, value=value, repeat_index=repeat_index))
            return answer_ids
        except KYCRecord.DoesNotExist as e:
            self.__class__.logger.error(f"Unable to process due to inability to find KYC Record with primary key: {record_pk}\n\t{e}")
            raise # Important to stop the transaction
        except (ValidationError, Exception) as e:
            self.__class__.logger.error(f"{e}")
            raise # Important to stop the transaction
        
    
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
    #queryset = KycQuestion.objects.all()
    permission_classes = [IsAuthenticated]

    queryset = KycQuestion.objects.prefetch_related(
        "conditions__dependencies__source_question",
        "conditions__dependencies__group",
    )

    serializer_class = KycQuestionSerializer


# Redis connection (reuse your existing Redis)
redis_client = redis.Redis.from_url(settings.REDIS_URL)

# SSE helper
def sse_event(data, event=None):
    msg = f"data: {json.dumps(data)}\n\n"
    if event:
        msg = f"event: {event}\n{msg}"
    return msg
