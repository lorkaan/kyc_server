from django.shortcuts import render
from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework.response import Response

from base.serializers import HistoryEventSerializer
from .models import Person
from .serializers import PersonSerializer

# Create your views here.
class PersonViewSet(ModelViewSet):
    queryset = Person.objects.all()
    serializer_class = PersonSerializer

    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        person = self.get_object()
        events = person.pghistory_events.all().order_by("-pgh_created_at")

        serializer = HistoryEventSerializer(events, many=True)
        return Response(serializer.data)
