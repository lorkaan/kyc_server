from django.shortcuts import render
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

class BaseViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]

# Create your views here.
