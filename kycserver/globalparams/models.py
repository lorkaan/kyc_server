from django.db import models

from base.models import GenericTargetMixin
from datetime import datetime
import uuid

class BaseValue(models.Model):

    parameter = models.OneToOneField(
        "GlobalParameter",
        on_delete=models.CASCADE,
        related_name="%(class)s",
        null=True,
        blank=True,
    )

    class Meta:
        abstract = True

    def get_value(self):
        """Return the raw value or perform preprocessing for custom types"""
        return self.value

class StringValue(BaseValue):
    value = models.CharField(max_length=255)

class JsonValue(BaseValue):
    value = models.JSONField()

class IntValue(BaseValue):
    value = models.IntegerField()

class FloatValue(BaseValue):
    value = models.FloatField()

class BooleanValue(BaseValue):
    value = models.BooleanField()

class UUIDValue(BaseValue):
    value = models.UUIDField(default=uuid.uuid4)

class DateTimeValue(BaseValue):
    value = models.DateTimeField()

# Create your models here.
class GlobalParameter(GenericTargetMixin):

    class Type(models.TextChoices):
        STRING = "S", "String"
        INT = "I", "Integer"
        FLOAT = "F", "Float"
        BOOLEAN = "B", "Boolean"
        UUID = "U", "UUID"
        DATETIME = "D", "Datetime"
        JSON = "J", "JSON"

    TYPE_MAP = {
            Type.STRING: str,
            Type.INT: int,
            Type.FLOAT: float,
            Type.BOOLEAN: bool,
            Type.UUID: uuid.UUID,
            Type.DATETIME: datetime,
            Type.JSON: object
        }

    description = models.TextField(blank=True)

    name = models.CharField(max_length=255, unique=True, null=False, blank=False)

    is_active = models.BooleanField(default=True)

    type = models.CharField(
        max_length=1,
        choices=Type.choices,
        default=Type.STRING,
    )

    def set_target(self, obj):
        if not isinstance(obj, BaseValue):
            raise TypeError(f"{obj} is not assignable as a Value for a parameter")
        obj.parameter = self
        obj.save()
        return super().set_target(obj)

    def get_value(self):
        """
        Return the resolved value of the parameter.
        Custom value objects (with get_value) are evaluated.
        The result is validated against the declared type.
        """
        if not self.content_object:
            return None
        if not isinstance(self.content_object, BaseValue):
            raise TypeError(f"{self.content_object} is not an accepted Value for a parameter")

        val = self.content_object.get_value()

        # Map single-char codes to Python types
        expected_type = self.TYPE_MAP.get(self.type)
        if expected_type and not isinstance(val, expected_type):
            raise TypeError(f"GlobalParameter {self.name} expected {expected_type} but got {type(val)}")

        return val

    def __str__(self):
        return f"{self.name} ({self.get_type_display()})"