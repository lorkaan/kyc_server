from django.db import models
import uuid
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


# Create your models here.

class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

class GenericTargetMixin(models.Model):
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE
    )
    object_id = models.UUIDField()

    content_object = GenericForeignKey(
        'content_type',
        'object_id'
    )

    class Meta:
        abstract = True

    def set_target(self, obj):
        self.content_type = ContentType.objects.get_for_model(obj)
        self.object_id = obj.pk

class NullableGenericTargetMixin(models.Model):
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    object_id = models.UUIDField(null=True, blank=True)

    content_object = GenericForeignKey(
        'content_type',
        'object_id'
    )

    class Meta:
        abstract = True
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(content_type__isnull=True, object_id__isnull=True) |
                    models.Q(content_type__isnull=False, object_id__isnull=False)
                ),
                name="valid_generic_relation"
            )
        ]

    def set_target(self, obj):
        """
        Assigns a target object, or clears it if obj is None.
        """
        if obj is None:
            self.content_type = None
            self.object_id = None
        else:
            self.content_type = ContentType.objects.get_for_model(obj)
            self.object_id = obj.pk

class GenericPointerToClassMixin(models.Model):
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE
    )

    class Meta:
        abstract = True

    def set_model(self, model_or_instance):
        """
        Accepts either a model class or instance
        """
        self.content_type = ContentType.objects.get_for_model(
            model_or_instance,
            for_concrete_model=False
        )

    def get_model_class(self):
        return self.content_type.model_class()
    
    def __str__(self):
        model = self.content_type.model
        return f"{model}.{self.field_name} → {self.label}"