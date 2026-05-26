from django.shortcuts import render
from utils.dict_utils import isDict
from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status

from base.serializers import HistoryEventSerializer
from .models import Alert, AlertSeverity, AlertStatus
from .serializers import AlertSerializer, AlertSeveritySerializer, AlertStatusSerializer

# Create your views here.

class AlertStatusViewSet(ModelViewSet):
    queryset = AlertStatus.objects.all().order_by("name")
    serializer_class = AlertStatusSerializer
    lookup_field = "id"  # optional (default anyway)


class AlertSeverityViewSet(ModelViewSet):
    queryset = AlertSeverity.objects.all().order_by("rank")
    serializer_class = AlertSeveritySerializer
    lookup_field = "id"

class AlertViewSet(ModelViewSet):
    queryset = Alert.objects.all()
    serializer_class = AlertSerializer

    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        alert = self.get_object()
        events = alert.pghistory_events.all().order_by("-pgh_created_at")
        serializer = HistoryEventSerializer(events, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=["post"])
    def edit(self, request, pk=None):
        cur_alert = self.get_object()

        payload = request.data.get("alert")

        if isDict(payload, keys=['alert']):
            payload = payload.get('alert', None)

        import logging
        logger = logging.getLogger()
        logger.error(f"Payload is: {payload}")

        if payload is None:
            return Response(
                {"detail": "Missing 'alert' payload."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payload.pop("content_type", None)
        payload.pop("object_id", None)
        payload.pop("content_object", None)
        payload.pop("target", None)

        try:
            serializer = AlertSerializer(
                cur_alert,
                data=payload,
                partial=True
            )

            serializer.is_valid(raise_exception=True)

            updated_alert = serializer.save()

            # Force DB refresh to verify persistence
            updated_alert.refresh_from_db()

            return Response(
                {
                    "success": True,
                    "updated": AlertSerializer(updated_alert).data
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                {"Error": f"{e}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )