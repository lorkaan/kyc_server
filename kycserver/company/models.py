from django.db import models

# Create your models here.
from kyc.models import ReferenceValue
import pghistory
from django.db import models
from django.core.exceptions import ValidationError

from base.models import BaseModel, ModelSchemaMixin

@pghistory.track()
class Company(ModelSchemaMixin, BaseModel):
    name = models.CharField(max_length=255)
    registration_number = models.CharField(max_length=100)
    country = models.ForeignKey(
        ReferenceValue,
        on_delete=models.PROTECT,
        related_name="companies",
        limit_choices_to={"reference_set__key": "countries"}
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name
    
    def clean(self):
        if self.country.reference_set.key != "countries":
            raise ValidationError("Country must come from 'countries' reference set")
        
    def save(self, *args, **kwargs):
        self.full_clean()  # <-- enforce validation
        super().save(*args, **kwargs)
        
    class Meta:
        unique_together = ("country", "registration_number")
        ordering = ["name"]

