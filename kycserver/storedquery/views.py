from django.forms import ValidationError
from django.shortcuts import render
from django.db import models
from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework.response import Response
from django.apps import apps
from django.db.models import Q
from rest_framework.permissions import IsAuthenticated

from utils.queryAstHandler import QueryAstHandler

from .models import SavedQuery, SavedQueryPermission
from .serializers import SavedQuerySerializer, SavedQueryPermissionSerializer

ALLOWED_MODELS = {
    "kyc.RelationshipRole",
    "kyc.PersonCompanyRelationship",
    "kyc.KYCStatus",
    "kyc.KYCRecord",
    "kyc.KycAnswer",
    "person.Person",
    "company.Company",
    "watchdog.AlertStatus",
    "watchdog.AlertSeverity",
    "watchdog.AlertReason",
    "watchdog.Alert",
    "watchdog.SignalSeverity",
    "watchdog.SignalType",
    "watchdog.Signal"
}

def run_saved_query(saved_query):
    query_results = QueryAstHandler.run(saved_query)


# Create your views here.
class SavedQueryViewSet(ModelViewSet):

    permission_classes = [IsAuthenticated]

    queryset = SavedQuery.objects.all()
    serializer_class = SavedQuerySerializer

    def get_queryset(self):
        user = self.request.user

        if user.is_superuser:
            return SavedQuery.objects.all()

        return SavedQuery.objects.filter(
            Q(is_system=True) |
            Q(owner=user) |
            Q(
                permissions__target_type=SavedQueryPermission.TargetType.ALL
            ) |
            Q(
                permissions__target_type=SavedQueryPermission.TargetType.USER,
                permissions__target_id=str(user.id)
            )
        ).distinct()
    
    @classmethod
    def apply_extra_options(cls, qs, extra_options):
        # -----------------------
        # 1. Apply additional filters
        # -----------------------
        filters = extra_options.get("filters")
        if filters and isinstance(filters, dict):
            qs = qs.filter(**filters)

        # -----------------------
        # 2. Apply ordering
        # -----------------------
        order_by = extra_options.get("order_by")
        if order_by:
            if isinstance(order_by, str):
                order_by = [order_by]
            qs = qs.order_by(*order_by)

        # -----------------------
        # 3. Apply limit
        # -----------------------
        limit = extra_options.get("limit")
        if limit:
            try:
                limit = int(limit)
                qs = qs[:limit]
            except ValueError:
                pass  # ignore invalid limit

        return qs

    @action(detail=True, methods=["get"])
    def permissions(self, request, pk=None):
        query = self.get_object()
        serializer = SavedQueryPermissionSerializer(
            query.permissions.all(), many=True
        )
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def run(self, request, pk=None):
        query = self.get_object()
        params = request.data.get("params", {})       # Bind params into AST
        extra_options = {
            "order_by": request.data.get("order_by"),
            "limit": request.data.get("limit"),
            "filters": request.data.get("filters")    # additional ad-hoc filtering
        }

        query_results = QueryAstHandler.run(query.to_ast_payload(), params)

        data = {}
        data["results"] = list(self.__class__.apply_extra_options(query_results, extra_options).values())

        return Response(data)

