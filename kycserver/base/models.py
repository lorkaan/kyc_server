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
    
class ModelSchemaMixin:
    @classmethod
    def get_schema(
        cls,
        include_choices=True,
        include_labels=True,
        choice_limit=100,
        filter_functions=None,  # dict: field_name -> callable(queryset)
    ):
        schema = {}

        for field in cls._meta.get_fields():
            if field.auto_created and not field.concrete:
                continue

            field_info = {
                "type": field.__class__.__name__,
                "required": not getattr(field, "blank", False),
                "null": getattr(field, "null", False),
            }

            # Char/Text choices
            if include_choices and hasattr(field, "choices") and field.choices:
                field_info["choices"] = [
                    {"value": choice[0], **({"label": choice[1]} if include_labels else {})}
                    for choice in field.choices
                ]

            # ForeignKey choices
            if isinstance(field, models.ForeignKey) and include_choices:
                queryset = field.related_model.objects.all()

                if field.limit_choices_to:
                    queryset = queryset.filter(**field.limit_choices_to)

                # Apply per-field filter if exists
                if filter_functions and field.name in filter_functions:
                    func = filter_functions[field.name]
                    if callable(func):
                        queryset = func(queryset)

                if choice_limit is not None:
                    queryset = queryset[:choice_limit]

                field_info["choices"] = [
                    {"id": obj.pk, **({"label": getattr(obj, "label", str(obj))} if include_labels else {})}
                    for obj in queryset
                ]

                field_info["related_model"] = field.related_model.__name__

            schema[field.name] = field_info

        return schema