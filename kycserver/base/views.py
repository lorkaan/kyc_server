from django.shortcuts import render
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated

class BaseViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated]

# Create your views here.
