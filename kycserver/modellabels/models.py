from django.db import models

from base.models import GenericPointerToClassMixin

# Create your models here.
class ModelFieldLabel(GenericPointerToClassMixin):
    field_name = models.CharField(max_length=255)  # e.g., "person__name"
    label = models.CharField(max_length=255)       # Human-readable
    description = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ('content_type', 'field_name')