from django.shortcuts import render
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated

from base.serializers import HistoryEventSerializer
from .models import KYCRecord, KycAnswer
from .serializers import KYCRecordSerializer



# Create your views here.
class KYCRecordViewSet(ModelViewSet):
    queryset = KYCRecord.objects.all()
    serializer_class = KYCRecordSerializer

    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        record = self.get_object()
        events = record.pghistory_events.all().order_by("-pgh_created_at")

        serializer = HistoryEventSerializer(events, many=True)
        return Response(serializer.data)

class KycAnswerViewSet(ModelViewSet):

    queryset = KycAnswer.objects.all()
    permission_classes = [IsAuthenticated]

    @action(
        detail=True,
        methods=["post"],
        parser_classes=[MultiPartParser]
    )
    def upload(self, request, pk=None):
        # Just in case
        if not request.user.is_authenticated:
            return Response(status=401)

        answer = self.get_object()
        file = request.FILES.get("file")

        if not file:
            return Response(
                {"error": "No file uploaded"},
                status=400
            )

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