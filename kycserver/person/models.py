from django.db import models
import pghistory

from base.models import BaseModel

# Create your models here.
@pghistory.track()
class Person(BaseModel):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField()

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

