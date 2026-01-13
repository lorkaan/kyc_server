from django.db import models

# Create your models here.
import pghistory
from django.db import models

from base.models import BaseModel

@pghistory.track()
class Company(BaseModel):
    name = models.CharField(max_length=255)
    registration_number = models.CharField(max_length=100, unique=True)
    country = models.CharField(max_length=2)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

