from django.shortcuts import render
from django.db import models
from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import SavedQuery, SavedQueryPermission
from .serializers import SavedQuerySerializer, SavedQueryPermissionSerializer

# Create your views here.
class SavedQueryViewSet(ModelViewSet):
    queryset = SavedQuery.objects.all()
    serializer_class = SavedQuerySerializer

    def get_queryset(self):
        user = self.request.user

        if user.is_superuser:
            return SavedQuery.objects.all()

        return SavedQuery.objects.filter(
            models.Q(is_system=True) |
            models.Q(owner=user) |
            models.Q(
                permissions__target_type=SavedQueryPermission.TargetType.ALL
            ) |
            models.Q(
                permissions__target_type=SavedQueryPermission.TargetType.USER,
                permissions__target_id=str(user.id)
            )
        ).distinct()

    @action(detail=True, methods=["get"])
    def permissions(self, request, pk=None):
        query = self.get_object()
        serializer = SavedQueryPermissionSerializer(
            query.permissions.all(), many=True
        )
        return Response(serializer.data)
