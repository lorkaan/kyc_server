from django.shortcuts import render
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from base.serializers import HistoryEventSerializer
from .models import KYCRecord
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
