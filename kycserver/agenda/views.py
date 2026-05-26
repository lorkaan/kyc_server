from rest_framework import viewsets, filters
from rest_framework.views import APIView
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import AgendaEventType, AgendaEvent
from .serializers import AgendaEventTypeSerializer, AgendaEventSerializer


class AgendaEventTypeViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing AgendaEventType
    """
    queryset = AgendaEventType.objects.all()
    serializer_class = AgendaEventTypeSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "description"]
    ordering_fields = ["name"]
    ordering = ["name"]


class AgendaEventViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing AgendaEvent
    """
    queryset = AgendaEvent.objects.select_related("event_type", "organizer").all()
    serializer_class = AgendaEventSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    
    filterset_fields = ["status", "event_type", "organizer", "all_day"]
    search_fields = ["title", "description", "location"]
    ordering_fields = ["start_time", "end_time", "title"]
    ordering = ["start_time"]

class EventStatusListView(APIView):
    def get(self, request):
        from .models import EventStatus

        return Response([
            {"value": choice.value, "label": choice.label}
            for choice in EventStatus
        ])