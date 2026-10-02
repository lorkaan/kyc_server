from decimal import Decimal

from django.db import models, transaction
from django.db.models import Sum
from django.utils import timezone
from base.models import BaseModel, GenericTargetMixin, ModelSchemaMixin
from django.utils.module_loading import import_string
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
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

        # ---------------------------------
        # Key conversion handling
        # ---------------------------------

        if issubclass(Serializer, KeyConversionSerializer):

            # avoid mutating original payload
            data = data.copy()
            for k, v in Serializer.CONVERSION_KEYS.items():
                logger.error(f"Checking key: {k}")
                # preserve existing behavior safely
                if k in data:
                    data[v] = data.get(k, None)
                    del data[k]
        logger.error(f"Transformed data for {data}")

        # ---------------------------------
        # Serializer validation + save
        # ---------------------------------

        try:
            serializer = Serializer(data=data)

            # IMPORTANT FIX:
            # raise validation errors properly
            serializer.is_valid(raise_exception=True)
            logger.error(
                f"Validated data: {serializer.validated_data}"
            )
            return serializer.save()
        except ValidationError as e:
            logger.error(
                f"Validation errors: {e}"
            )
            raise
        except Exception as e:
            logger.error(
                f"Error in Serializer Validation: {e}"
            )
            raise

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
        if self.name == "":
            self.name = None
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

    contact = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["party", "target_party", "role", "start_date"],
                name="unique_party_relationship"
            ),
            models.CheckConstraint(
                condition=(models.Q(end_date__isnull=True) | models.Q(end_date__gte=models.F("start_date"))),
                name="end_date_after_start_date"
            ),
            models.CheckConstraint(
                condition=~models.Q(party=models.F("target_party")),
                name="prevent_self_relationship"
            )
        ]

    @property
    def active_metadata(self):
        return self.metadata.filter(is_active=True).first()

class PartyRelationshipCode(models.Model):
    code = models.PositiveIntegerField(validators=[MinValueValidator(1)], unique=True)
    label = models.CharField(max_length=255)
    description = models.TextField()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(code__gte=1),
                name="code_gte_1"
            )
        ]

class PercentageValidationMixin:

    PERCENTAGE_FIELDS = []

    def get_percentage_scope(self):
        raise NotImplementedError

    @classmethod
    def validate_percentage_total(cls, instance, field_name, scope_filter):
        value = getattr(instance, field_name)

        if value is None:
            return

        qs = instance.__class__.objects.filter(**scope_filter)

        if instance.pk:
            qs = qs.exclude(pk=instance.pk)

        total = qs.aggregate(total=Sum(field_name))["total"] or Decimal("0")

        if total + value > Decimal("100"):
            raise ValidationError({
                field_name: "Total cannot exceed 100.0000"
            })

    def validate_percentages(self):
        if not self.pk and not getattr(self, "relationship_id", None):
            return

        scope = self.get_percentage_scope()

        for field in self.PERCENTAGE_FIELDS:
            self.__class__.validate_percentage_total(self, field, scope)

@pghistory.track()
class PartyRelationshipMetadata(BaseModel, PercentageValidationMixin):

    PERCENTAGE_FIELDS = [
        "share_percentage",
        "voting_rights_percentage",
    ]

    relationship = models.ForeignKey( # This could potentially have multiple, watch out for that.
        PartyRelationship,
        on_delete=models.CASCADE,
        related_name="metadata"
    )

    details = models.TextField(blank=True, null=True)

    share_percentage = models.DecimalField(
        max_digits=7,          # supports up to 100.0000
        decimal_places=4,
        null=True, 
        blank=True,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(100),
        ]
    )

    voting_rights_percentage = models.DecimalField(
            max_digits=7,          # supports up to 100.0000
            decimal_places=4,
            null=True, 
            blank=True,
            validators=[
                MinValueValidator(0),
                MaxValueValidator(100),
            ]
        )

    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["relationship"],
                condition=models.Q(is_active=True),
                name="unique_active_metadata_per_relationship"
            )
        ]

    def get_percentage_scope(self):
        return {
            "relationship__target_party": self.relationship.target_party
        }
    
    def clean(self):
        super().clean()

        if not self.relationship_id:
            return  # can't validate yet

        self.validate_percentages()

    def save(self, *args, **kwargs):
        with transaction.atomic():

            # If this is being saved as active
            if self.is_active and self.relationship_id:

                (
                    self.__class__.objects
                    .filter(
                        relationship=self.relationship,
                        is_active=True
                    )
                    .exclude(pk=self.pk)
                    .update(is_active=False)
                )

            # Run validation AFTER deactivation to avoid constraint issues
            self.full_clean()

            super().save(*args, **kwargs)

@pghistory.track()
class PartyRelationshipMetadataCode(BaseModel):
    metadata = models.ForeignKey(
        PartyRelationshipMetadata,
        on_delete=models.CASCADE,
        related_name="codes"
    )

    code = models.ForeignKey(
        PartyRelationshipCode,
        on_delete=models.CASCADE,
        related_name="metadata_codes"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["metadata", "code"],
                name="unique_metadata_code"
            )
        ]

