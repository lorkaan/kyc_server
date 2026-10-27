from django.shortcuts import render
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

class BaseViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]

    @classmethod
    def stringifyRequest(cls, request):
        print("USER:", request.user)
        print("AUTH:", request.auth)
        print("AUTHENTICATED:", request.user.is_authenticated)
        print("COOKIES:", request.COOKIES)

        return f"USER: {request.user}\n\tAUTH: {request.auth}\n\tAUTHENTICATED: {request.user.is_authenticated}\n\tCOOKIES: {request.COOKIES}"

# Create your views here.
