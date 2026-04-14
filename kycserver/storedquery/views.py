import json
import time

from django.forms import ValidationError
from django.shortcuts import render
from django.db import models
from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework.response import Response
from django.apps import apps
from django.db.models import Q
from rest_framework.permissions import IsAuthenticated

from utils.queryAstHandler import AnnotatedQueryAstHandler, QueryAstHandler

from .models import SavedQuery, SavedQueryPermission
from .serializers import SavedQuerySerializer, SavedQueryPermissionSerializer
from utils.type_utils import isList
import csv
from django.http import HttpResponse
from django.utils import timezone
import re


ALLOWED_MODELS = {
    "kyc.RelationshipRole",
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

    @classmethod
    def sanitize_filename(cls, name):
        return re.sub(r"[^A-Za-z0-9_-]", "_", name)

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
    
    def execute_query(self, request, post_flag=True, query_result_return=False):
        query = self.get_object()
        if post_flag:
            data = request.data
        else:
            data = request.query_params
        params = data.get("params", {})       # Bind params into AST
        extra_options = {
            "order_by": data.get("order_by"),
            "limit": data.get("limit"),
            "filters": data.get("filters")    # additional ad-hoc filtering
        }
        query_results = AnnotatedQueryAstHandler.run(query.to_ast_payload(), params, annotateFlag = not query_result_return)
        if not query_result_return:
            return list(self.__class__.apply_extra_options(query_results, extra_options).values())
        else:
            return self.__class__.apply_extra_options(query_results, extra_options)
    
    @action(detail=True, methods=['post'])
    def run(self, request, pk=None):
        data = {}
        data["results"] = self.execute_query(request)
        return Response(data)
    
    @action(detail=True, methods=['post'])
    def download(self, request, pk=None):
        rows = self.execute_query(request)
        name = request.data.get("name", "Untitled")
        timestamp = timezone.localtime().strftime("%Y%m%d_%H%M%S")
        if isList(rows):
            field_labels_override = request.data.get("field_labels", {})
            selected_fields = request.data.get("selected_fields", [])
            if not isList(selected_fields):
                selected_fields = list(rows[0].keys())
            from modellabels.utils import get_field_label
            model_class = self.get_object().get_model_class()  # You should have a method returning the Django model for this query
            headers = [
                get_field_label(model_class, f, override=field_labels_override)
                for f in selected_fields
            ]

            response = HttpResponse(
                content_type="text/csv"
            )
            filename = f"{self.__class__.sanitize_filename(name)}_{timestamp}.csv"
            response["Content-Disposition"] = (
                f'attachment; filename="{filename}"'
            )

            writer = csv.writer(response)

            writer.writerow(headers)

            for row in rows:
                writer.writerow([row.get(f, "") for f in selected_fields])

            return response
        else:
            return HttpResponse(status=404)
