from django.db import models
import pghistory

from base.models import BaseModel, ModelSchemaMixin

# Create your models here.
@pghistory.track()
class Person(ModelSchemaMixin, BaseModel):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    date_of_death = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    
    def get_serializer_class(self):
        from .serializers import PersonSerializer
        return PersonSerializer

