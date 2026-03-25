from django.db import models
from django.utils import timezone
from base.models import BaseModel, GenericTargetMixin
from django.utils.module_loading import import_string
from utils.dict_utils import dictToStr
import pghistory
import logging

# Create your models here.
class PartyType(models.Model):

    logger = logging.getLogger()

    code = models.SlugField(unique=True)

    name = models.CharField(max_length=100)

    description = models.TextField(blank=True)

    serializer_path = models.CharField(max_length=255)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(default=timezone.now)

    def get_serializer(self):
        return import_string(self.serializer_path)

    def create_entity(self, data):
        self.__class__.logger.error(f"Entity Data\n: {dictToStr(data, prefix="\t")}")
        Serializer = self.get_serializer()
        serializer = Serializer(data=data)
        #self.__class__.logger.error(f"Prevalidation Data\n: {dictToStr(serializer.data, prefix="\t")}")
        try:
            serializer.is_valid(raise_exception=True)
        except Exception as e:
            self.__class__.logger.error(f"Validation Error in Serializer: {e}")
        self.__class__.logger.error(f"PostValidation Data\n: {dictToStr(serializer.data, prefix="\t")}")
        return serializer.save()

    def __str__(self):
        return self.name
    
@pghistory.track()
class Party(GenericTargetMixin, BaseModel):

    party_type = models.ForeignKey(
        PartyType,
        on_delete=models.PROTECT,
        related_name="parties"
    )

    name = models.CharField(max_length=255)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name
    
    class Meta:
        constraints = [
            # prevent multiple Party rows pointing to the same entity
            models.UniqueConstraint(
                fields=["content_type", "object_id"],
                name="unique_party_entity"
            )
        ]
    
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