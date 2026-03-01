from django.db import models, transaction
from django.db.models import Q
from django.forms import ValidationError
import pghistory
from django.core.exceptions import ValidationError

from base.models import BaseModel
from company.models import Company
from users.models import User
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

    is_current = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["person"],
                condition=Q(is_current=True),
                name="one_current_kyc_per_person"
            )
        ]

    def clean(self):
        """
        Enforce KYC current-record semantics.
        """
        existing_current = (
            KYCRecord.objects
            .filter(person=self.person, is_current=True)
            .exclude(pk=self.pk)
            .exists()
        )

        if existing_current and not self.is_current:
            raise ValidationError(
                "A current KYC record already exists for this person. "
                "You must explicitly set is_current=True to replace it."
            )
    
    def save(self, *args, **kwargs):
        """
        Atomic enforcement of:
        - default current if none exists
        - demotion of previous current when replacing
        """
        with transaction.atomic():
            is_new = self.pk is None

            if is_new:
                has_current = (
                    KYCRecord.objects
                    .filter(person=self.person, is_current=True)
                    .exists()
                )

                # Rule 1: auto-promote if none exists
                if not has_current and self.is_current is False:
                    self.is_current = True

            # Run validation
            self.full_clean()

            super().save(*args, **kwargs)

            # Rule 3: demote all others if explicitly current
            if self.is_current:
                (
                    KYCRecord.objects
                    .filter(person=self.person, is_current=True)
                    .exclude(pk=self.pk)
                    .update(is_current=False)
                )

@pghistory.track()
class KycQuestion(models.Model):
    class AnswerTypeEnum(models.TextChoices):
        NUMBER = "N", "number"
        TEXT   = "T", "text"
        BOOL   = "B", "bool"
        SINGLE = "S", "single"
        MULTI  = "M", "multi"

    key = models.SlugField(unique=True)
    label = models.CharField(max_length=255)
    answer_type = models.CharField(max_length=1, choices=AnswerTypeEnum)
    required = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    requires_document = models.BooleanField(default=False)

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

        if self.question.requires_document:
            if not self.attachments.exists():
                raise ValidationError("Supporting document required")

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

"""
Validation for a file
"""
def validate_file(file):

    max_size = 10 * 1024 * 1024  # 10MB

    if file.size > max_size:
        raise ValidationError("File too large (max 10MB)")

    allowed = [
        "application/pdf",
        "image/jpeg",
        "image/png"
    ]

    if file.content_type not in allowed:
        raise ValidationError("Unsupported file type")

@pghistory.track()
class KycAnswerAttachment(BaseModel):

    answer = models.ForeignKey(
        KycAnswer,
        on_delete=models.CASCADE,
        related_name="attachments"
    )

    file = models.FileField(
        upload_to="kyc/answers/%Y/%m/%d/",
        validators=[validate_file]
    )

    original_name = models.CharField(max_length=255)

    content_type = models.CharField(max_length=100)

    size = models.BigIntegerField()

    uploaded_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    description = models.TextField(blank=True)

    class Meta:
        ordering = ["created_at", "updated_at"]

    def __str__(self):
        return self.original_name