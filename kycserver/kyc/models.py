from django.db import models
import pghistory

from base.models import BaseModel
from company.models import Company
from person.models import Person

# Create your models here.
@pghistory.track(
    pghistory.Snapshot("person_company_snapshot"),
    pghistory.InsertEvent("relationship_created"),
    pghistory.UpdateEvent("relationship_updated"),
)
class PersonCompanyRelationship(BaseModel):
    ROLE_CHOICES = [
        ("director", "Director"),
        ("owner", "Owner"),
        ("employee", "Employee"),
        ("beneficial_owner", "Beneficial Owner"),
    ]

    person = models.ForeignKey(Person, on_delete=models.CASCADE)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    role = models.CharField(max_length=50, choices=ROLE_CHOICES)
    ownership_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = ("person", "company", "role", "start_date")

@pghistory.track(
    pghistory.Snapshot("kyc_snapshot"),
    pghistory.InsertEvent("kyc_created"),
)
class KYCRecord(BaseModel):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("expired", "Expired"),
    ]

    person = models.ForeignKey(
        Person, on_delete=models.CASCADE, related_name="kyc_records"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    risk_score = models.IntegerField()
    notes = models.TextField(blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)

