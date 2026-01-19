from django.db import models
from django.forms import ValidationError
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

@pghistory.track()
class KycQuestion(models.Model):
    NUMBER = "number"
    TEXT = "text"
    BOOL = "bool"
    SINGLE = "single"
    MULTI = "multi"

    ANSWER_TYPE_CHOICES = [
        (NUMBER, "N"),
        (TEXT, "T"),
        (BOOL, "B"),
        (SINGLE, "S"),
        (MULTI, "M"),
    ]

    key = models.SlugField(unique=True)
    label = models.CharField(max_length=255)
    answer_type = models.CharField(max_length=1, choices=ANSWER_TYPE_CHOICES)
    required = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.label

@pghistory.track()
class KycQuestionOption(models.Model):
    question = models.ForeignKey(
        KycQuestion,
        on_delete=models.CASCADE,
        related_name="options"
    )
    value = models.CharField(max_length=100)
    label = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("question", "value")
        ordering = ["order"]

    def __str__(self):
        return self.label

@pghistory.track()
class KycAnswer(models.Model):
    kyc_record = models.ForeignKey(
        KYCRecord,
        on_delete=models.CASCADE,
        related_name="answers"
    )
    question = models.ForeignKey(
        KycQuestion,
        on_delete=models.CASCADE
    )

    value_number = models.DecimalField(
        max_digits=20, decimal_places=2,
        null=True, blank=True
    )
    value_text = models.TextField(null=True, blank=True)
    value_bool = models.BooleanField(null=True, blank=True)

    value_option = models.ForeignKey(
        KycQuestionOption,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    class Meta:
        unique_together = ("kyc_record", "question")

    # 👇 IT GOES HERE
    def clean(self):
        super().clean()

        t = self.question.answer_type

        has_multi = self.pk and self.selected_options.exists()

        has_value = any([
            self.value_number is not None,
            bool(self.value_text),
            self.value_bool is not None,
            self.value_option is not None,
            has_multi
        ])

        # Optional question → unanswered is OK
        if not self.question.required and not has_value:
            return

        # Required question → must be answered
        if self.question.required and not has_value:
            raise ValidationError("This question requires an answer.")

        # Type enforcement
        if t == KycQuestion.NUMBER and self.value_number is None:
            raise ValidationError("Number answer required")

        if t == KycQuestion.TEXT and not self.value_text:
            raise ValidationError("Text answer required")

        if t == KycQuestion.BOOL and self.value_bool is None:
            raise ValidationError("Boolean answer required")

        if t == KycQuestion.SINGLE:
            if self.value_option is None:
                raise ValidationError("Exactly one option must be selected")
            if has_multi:
                raise ValidationError("Single choice cannot have multiple options")

        if t == KycQuestion.MULTI:
            if self.value_option is not None:
                raise ValidationError("Multi choice cannot have a single option")
            if self.question.required and not has_multi:
                raise ValidationError("At least one option must be selected")
        
            # Ensure all selected options belong to the question
            invalid = self.selected_options.exclude(
                option__question=self.question
            ).exists()
            if invalid:
                raise ValidationError("One or more selected options are invalid")
                
@pghistory.track()
class KycAnswerOption(models.Model):
    answer = models.ForeignKey(
        KycAnswer,
        on_delete=models.CASCADE,
        related_name="selected_options"
    )
    option = models.ForeignKey(
        KycQuestionOption,
        on_delete=models.CASCADE
    )

    class Meta:
        unique_together = ("answer", "option")