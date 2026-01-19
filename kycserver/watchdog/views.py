from django.shortcuts import render
from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework.response import Response

from ..base.serializers import HistoryEventSerializer
from .models import Alert
from .serializers import AlertSerializer

# Create your views here.
class AlertViewSet(ModelViewSet):
    queryset = Alert.objects.all()
    serializer_class = AlertSerializer

    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        alert = self.get_object()
        events = alert.pghistory_events.all().order_by("-pgh_created_at")
        serializer = HistoryEventSerializer(events, many=True)
        return Response(serializer.data)
