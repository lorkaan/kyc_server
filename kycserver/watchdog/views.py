from django.shortcuts import render
from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status

from base.serializers import HistoryEventSerializer
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
    
    @action(detail=True, methods=["post"])
    def edit(self, request, pk=None):
        cur_alert = self.get_object()

        payload = request.data.get("alert")

        if payload is None:
            return Response(
                {"detail": "Missing 'alert' payload."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Prevent generic target fields from being overwritten
        payload.pop("content_type", None)
        payload.pop("object_id", None)
        payload.pop("content_object", None)
        payload.pop("target", None)

        serializer = AlertSerializer(
            cur_alert,
            data=payload,
            partial=True,
            context={"request": request},
        )

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )

        updated_alert = serializer.save()

        return Response(
            AlertSerializer(
                updated_alert,
                context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )