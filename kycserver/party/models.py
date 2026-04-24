from django.db import models
from django.utils import timezone
from base.models import BaseModel, GenericTargetMixin, ModelSchemaMixin
from django.utils.module_loading import import_string
from django.core.exceptions import ValidationError
import pghistory
import logging

# Create your models here.
class PartyType(models.Model):

    code = models.SlugField(unique=True)

    name = models.CharField(max_length=100)

    description = models.TextField(blank=True)

    serializer_path = models.CharField(max_length=255)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(default=timezone.now)

    def get_serializer(self):
        return import_string(self.serializer_path)
    
    def get_model(self):
        Serializer = self.get_serializer()
        return Serializer.Meta.model

    def create_entity(self, data):
        from base.serializers import KeyConversionSerializer
        logger = logging.getLogger()
        logger.error(f"Creating entity for {data}")
        Serializer = self.get_serializer()
        logger.error(f"\tUsing serializer for {Serializer}")
        if issubclass(Serializer, KeyConversionSerializer):
            for k, v in Serializer.CONVERSION_KEYS.items():
                logger.error(f"Checking key: {k}")
                data[v] = data.get(k, None)
                del data[k]
        logger.error(f"Transformed data for {data}")
        serializer = Serializer(data=data)
        #self.__class__.logger.error(f"Prevalidation Data\n: {dictToStr(serializer.data, prefix="\t")}")
        try:
            serializer.is_valid(raise_exception=True)
        except Exception as e:
            logger.error(f"Error in Serializer Validation: {e}")
            raise e
        return serializer.save()

    def __str__(self):
        return self.name

    def get_model_fields(self):
        model_cls = self.get_model()
        if issubclass(model_cls, ModelSchemaMixin):
            return model_cls.get_schema(choice_limit=None)
        else:
            return {}
    
@pghistory.track()
class Party(GenericTargetMixin, BaseModel):

    party_type = models.ForeignKey(
        PartyType,
        on_delete=models.PROTECT,
        related_name="parties"
    )

    name = models.CharField(max_length=255, blank=True, null=True)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name or f"Party {self.pk}"
    
    class Meta:
        constraints = [
            # prevent multiple Party rows pointing to the same entity
            models.UniqueConstraint(
                fields=["content_type", "object_id"],
                name="unique_party_entity"
            ),
            models.UniqueConstraint(
                fields=["name"],
                name="unique_party_name_not_null",
                condition=models.Q(name__isnull=False)
            )
        ]
    
    def clean(self):
        super().clean()  # in case GenericTargetMixin has validations

        # Ensure the content_object (target of the GenericForeignKey) inherits ModelSchemaMixin
        target_model = self.content_type.model_class()
        if not issubclass(target_model, ModelSchemaMixin):
            raise ValidationError(
                f"Party's target model must inherit from ModelSchemaMixin. "
                f"Got {target_model.__name__}"
            )

    def save(self, *args, **kwargs):
        self.full_clean()  # enforce validation before saving
        super().save(*args, **kwargs)
    
"""
Links a party to another party. Such as a Person to a Company
"""
@pghistory.track()
class PartyRelationship(BaseModel):
    party = models.ForeignKey(
        Party,
        on_delete=models.CASCADE,
        related_name="memberships"
    )

    # This party is the participant in another party (e.g., a person in a company)
    target_party = models.ForeignKey(
        Party,
        on_delete=models.CASCADE,
        related_name="participants"
    )

    role = models.ForeignKey(
        "kyc.RelationshipRole",
        on_delete=models.PROTECT,
        related_name="relationships"
    )

    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = ("party", "target_party", "role", "start_date")