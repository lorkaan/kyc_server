from django.db import models

# Create your models here.
from kyc.models import ReferenceValue
from kycserver.globalparams.models import GlobalParameter
import pghistory
from django.db import models
from django.core.exceptions import ValidationError

from base.models import BaseModel, ModelSchemaMixin

domestic_country_key = "Domestic"

@pghistory.track()
class Company(ModelSchemaMixin, BaseModel):
    name = models.CharField(max_length=255)
    registration_number = models.CharField(max_length=100)
    country = models.ForeignKey(
        ReferenceValue,
        on_delete=models.PROTECT,
        related_name="companies",
        limit_choices_to={"reference_set__key": "countries"},
        null=True,
        blank=True
    )

    is_domestic = models.BooleanField(default=False)

    opening_date = models.DateField()
    closeing_date = models.DateField(null=True, blank=True)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name
    
    @classmethod
    def get_domestic_country(cls):
        try:
            query = GlobalParameter.objects.get(name=domestic_country_key)
            cur_pk = query.get_value()
            try:
                ref_val = ReferenceValue.objects.get(pk=cur_pk)
                return ref_val
            except ReferenceValue.DoesNotExist:
                return None
        except GlobalParameter.DoesNotExist:
            return None
    
    def clean(self):
        if self.is_domestic:
            domestic_country = self.__class__.get_domestic_country()
            if isinstance(domestic_country, ReferenceValue) and domestic_country.reference_set.key == "countries":
                if self.country == None:
                    # Set the domestic country
                    self.country = domestic_country
                elif self.country.pk != domestic_country.pk:
                    raise ValidationError(f"{self.country.code} is not the Domestic Country -> ({self.country.pk}, {self.country.code}) != ({domestic_country.pk}, {domestic_country.code})")
        if not isinstance(self.country, ReferenceValue) or self.country.reference_set.key != "countries":
            raise ValidationError("Country must come from 'countries' reference set")

    def save(self, *args, **kwargs):
        self.full_clean()  # <-- enforce validation
        super().save(*args, **kwargs)

    def get_serializer_class(self):
        from .serializers import CompanySerializer
        return CompanySerializer
        
    class Meta:
        unique_together = ("country", "registration_number")
        ordering = ["name"]

