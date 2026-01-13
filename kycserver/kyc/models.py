from django.db import models
import pghistory

from base.models import BaseModel
from company.models import Company
from person.models import Person

# Create your models here.

class RelationshipRole(models.Model):
    """
    Reference table for allowed roles in a Person–Company relationship
    """
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_ownership_role = models.BooleanField(default=False)

    class Meta:
        db_table = "relationship_role"

    def __str__(self):
        return self.name

@pghistory.track()
class PersonCompanyRelationship(BaseModel):
    person = models.ForeignKey(Person, on_delete=models.CASCADE)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    role = models.ForeignKey(
        RelationshipRole,
        on_delete=models.PROTECT,
        related_name="relationships"
    )
    ownership_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = ("person", "company", "role", "start_date")

class KYCStatus(models.Model):
    """
    Reference table for KYC lifecycle statuses
    """
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=50)

    is_terminal = models.BooleanField(default=False)
    requires_review = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "kyc_status"

    def __str__(self):
        return self.name

@pghistory.track()
class KYCRecord(BaseModel):
    status = models.ForeignKey(
        KYCStatus,
        on_delete=models.PROTECT,
        related_name="kyc_records",
    )

    person = models.ForeignKey(
        Person, on_delete=models.CASCADE, related_name="kyc_records"
    )
    risk_score = models.IntegerField()
    notes = models.TextField(blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)


