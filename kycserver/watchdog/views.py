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

        new_alert = request.data.get("alert")

        if not new_alert:
            return Response(
                {"detail": "Missing 'alert' payload."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = AlertSerializer(
            cur_alert,
            data=new_alert,
            partial=True,
            context={"request": request},
        )

        if serializer.is_valid():
            updated_alert = serializer.save()

            return Response(
                AlertSerializer(
                    updated_alert,
                    context={"request": request},
                ).data,
                status=status.HTTP_200_OK,
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )