from django.db import models, transaction
from django.db.models import Q
from party.models import Party, PartyType
import pghistory
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils import timezone

from base.models import BaseModel
from company.models import Company
from users.models import User
from person.models import Person

# Create your models here.
"""
Constants designed to be global for controlling the KYC process via admin without
direct interference from the programmer
"""
@pghistory.track()
class KycRuleConstant(models.Model):
    """
    System-wide constants usable in conditions.
    """

    class ValueType(models.TextChoices):
        INT = "int", "Integer"
        FLOAT = "float", "Float"
        STRING = "string", "String"
        DATE = "date", "Date"
        BOOL = "bool", "Boolean"

    key = models.SlugField(unique=True)

    name = models.CharField(max_length=100)

    description = models.TextField(blank=True)

    value_type = models.CharField(
        max_length=20,
        choices=ValueType.choices
    )

    value_int = models.IntegerField(null=True, blank=True)
    value_float = models.FloatField(null=True, blank=True)
    value_string = models.CharField(max_length=255, null=True, blank=True)
    value_bool = models.BooleanField(null=True, blank=True)
    value_date = models.DateField(null=True, blank=True)

    is_active = models.BooleanField(default=True)

    updated_at = models.DateTimeField(default=timezone.now)

    def get_value(self):

        if self.value_type == self.ValueType.INT:
            return self.value_int

        if self.value_type == self.ValueType.FLOAT:
            return self.value_float

        if self.value_type == self.ValueType.STRING:
            return self.value_string

        if self.value_type == self.ValueType.BOOL:
            return self.value_bool

        if self.value_type == self.ValueType.DATE:
            return self.value_date

        return None

    def clean(self):

        fields = {
            "int": self.value_int,
            "float": self.value_float,
            "string": self.value_string,
            "bool": self.value_bool,
            "date": self.value_date,
        }

        filled = [v for v in fields.values() if v is not None]

        if len(filled) != 1:
            raise ValidationError(
                "Exactly one value field must be populated"
            )

    def __str__(self):
        return self.key

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
        "KYCStatus",
        on_delete=models.PROTECT,
        related_name="kyc_records",
    )
    party = models.ForeignKey(
        Party, on_delete=models.CASCADE, related_name="kyc_records",
        null=True,
        blank=True
    )
    risk_score = models.IntegerField()
    notes = models.TextField(blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    is_current = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["party"],
                condition=Q(is_current=True),
                name="one_current_kyc_per_party"
            )
        ]

    def clean(self):
        existing_current = (
            KYCRecord.objects
            .filter(party=self.party, is_current=True)
            .exclude(pk=self.pk)
            .exists()
        )
        if existing_current and not self.is_current:
            raise ValidationError(
                "A current KYC record already exists for this party. "
                "You must explicitly set is_current=True to replace it."
            )

    def save(self, *args, **kwargs):
        with transaction.atomic():
            is_new = self.pk is None
            if is_new:
                has_current = KYCRecord.objects.filter(
                    party=self.party, is_current=True
                ).exists()
                if not has_current and self.is_current is False:
                    self.is_current = True

            self.full_clean()
            super().save(*args, **kwargs)

            if self.is_current:
                KYCRecord.objects.filter(
                    party=self.party, is_current=True
                ).exclude(pk=self.pk).update(is_current=False)

@pghistory.track()
class KycQuestionGroup(models.Model):
    key = models.SlugField(unique=True)
    label = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)
    required = models.BooleanField(default=True)
    is_repeatable = models.BooleanField(default=False)  # NEW: repeatable group

    def __str__(self):
        return self.label

@pghistory.track()
class ReferenceSet(models.Model):
    """
    Master reference list (countries, titles, etc.)
    """
    key = models.SlugField(unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)

    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name
    
@pghistory.track()
class ReferenceValue(models.Model):
    """
    Values inside a reference set
    """
    reference_set = models.ForeignKey(
        ReferenceSet,
        on_delete=models.CASCADE,
        related_name="values"
    )

    code = models.CharField(max_length=20)   # e.g. US, CA, MR
    label = models.CharField(max_length=255) # United States
    order = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("reference_set", "code")
        ordering = ["order"]

    def __str__(self):
        return f"{self.label} ({self.code})"

@pghistory.track()
class KycQuestion(models.Model):

    class AnswerTypeEnum(models.TextChoices):
        NUMBER = "N", "number"
        TEXT   = "T", "text"
        BOOL   = "B", "bool"
        SINGLE = "S", "single"
        MULTI  = "M", "multi"
        DATE   = "D", "date"
        RANGE  = "R", "date_range"
        PHONE  = "P", "phone_number"
        EMAIL  = "E", "email_address"

    key = models.SlugField(unique=True)
    label = models.CharField(max_length=255)

    party_type = models.ForeignKey(
        PartyType,
        on_delete=models.PROTECT,
        related_name="kyc_questions",
        null=True,
        blank=True
    )

    group = models.ForeignKey(
        KycQuestionGroup,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="questions"
    )

    reference_set = models.ForeignKey(
        ReferenceSet,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="questions"
    )

    answer_type = models.CharField(max_length=1, choices=AnswerTypeEnum)
    required = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    requires_document = models.BooleanField(default=False)
    is_repeatable = models.BooleanField(default=False)  # NEW: repeatable question

    def __str__(self):
        return self.label
    
    def is_effectively_required(self, kyc_record):
        """
        Returns whether this question is required
        for a given KYC record, considering conditions.
        """

        # Base rule
        if not self.required:
            return False

        # Active REQUIRE conditions
        conditions = self.conditions.filter(
            is_active=True,
            condition_type=KycCondition.ConditionType.REQUIRE
        ).order_by("priority")

        # No overrides → base applies
        if not conditions.exists():
            return True

        # All conditions must pass
        for cond in conditions:
            if not cond.evaluate(kyc_record):
                return False

        return True
    
    def is_visible(self, kyc_record):
        conditions = self.conditions.filter(
            is_active=True,
            condition_type=KycCondition.ConditionType.SHOW
        )

        if not conditions.exists():
            return True

        return all(
            c.evaluate(kyc_record) for c in conditions
        )
        
    def clean(self):
        super().clean()

        # Choice questions must use reference sets
        if self.answer_type in {
            self.AnswerTypeEnum.SINGLE,
            self.AnswerTypeEnum.MULTI,
        }:
            if not self.reference_set:
                raise ValidationError(
                    "Single/Multi choice questions must have a reference set."
                )

        # Non-choice questions must NOT have reference sets
        if self.answer_type not in {
            self.AnswerTypeEnum.SINGLE,
            self.AnswerTypeEnum.MULTI,
        }:
            if self.reference_set:
                raise ValidationError(
                    "Only Single/Multi questions may use reference sets."
                )
            
@pghistory.track()
class KycCondition(models.Model):
    """
    A rule controlling visibility / requirement / validation of a question.
    """

    class ConditionType(models.TextChoices):
        SHOW = "show", "Show question"
        REQUIRE = "require", "Require answer"
        BLOCK = "block", "Block submission"
        VALIDATE = "validate", "Custom validation"

    target_question = models.ForeignKey(
        KycQuestion,
        on_delete=models.CASCADE,
        related_name="conditions"
    )

    condition_type = models.CharField(
        max_length=20,
        choices=ConditionType.choices
    )

    # BooleanLogicEngine-compatible JSON
    rule = models.JSONField()

    description = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)

    priority = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["priority", "id"]

    def __str__(self):
        return f"{self.target_question.key} [{self.condition_type}]"

@pghistory.track()
class KycConditionDependency(models.Model):
    """
    Declares which questions a condition depends on.
    """

    condition = models.ForeignKey(
        KycCondition,
        on_delete=models.CASCADE,
        related_name="dependencies"
    )

    source_question = models.ForeignKey(
        KycQuestion,
        on_delete=models.CASCADE,
        related_name="dependent_conditions"
    )

    # If dependency is inside a repeatable group
    group = models.ForeignKey(
        KycQuestionGroup,
        null=True,
        blank=True,
        on_delete=models.CASCADE
    )

    is_required = models.BooleanField(
        default=True,
        help_text="If false, missing value does not invalidate rule"
    )

    class Meta:
        unique_together = (
            "condition",
            "source_question",
            "group",
        )

    def __str__(self):
        return f"{self.condition} <- {self.source_question.key}"

phone_validator = RegexValidator(
    regex=r'^\+?\d{9,15}$',
    message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
)

@pghistory.track()
class KycAnswer(models.Model):

    kyc_record = models.ForeignKey(
        KYCRecord,
        on_delete=models.CASCADE,
        related_name="answers"
    )

    question = models.ForeignKey(
        KycQuestion,
        on_delete=models.CASCADE,
        related_name="answers"
    )

    repeat_index = models.PositiveIntegerField(default=0)

    # -----------------------
    # Scalar values
    # -----------------------

    value_number = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True
    )

    value_text = models.TextField(null=True, blank=True)

    value_bool = models.BooleanField(null=True, blank=True)

    value_reference = models.ForeignKey(
        ReferenceValue,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="single_answers"
    )

    value_date = models.DateField(null=True, blank=True)

    value_date_from = models.DateField(null=True, blank=True)
    value_date_to = models.DateField(null=True, blank=True)

    value_email = models.EmailField(null=True, blank=True)

    value_phone = models.CharField(
        max_length=16,
        null=True,
        blank=True,
        validators=[phone_validator],
        help_text="Enter phone number in international format"
    )

    # -----------------------

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["kyc_record", "question", "repeat_index"],
                name="unique_answer_instance"
            )
        ]

    # -------------------------------------------------
    # Value detection
    # -------------------------------------------------

    def has_value(self):

        has_multi = self.pk and self.selected_options.exists()

        has_range = (
            self.value_date_from is not None and
            self.value_date_to is not None
        )

        return any([
            self.value_number is not None,
            bool(self.value_text),
            self.value_bool is not None,
            self.value_reference is not None,
            self.value_date is not None,
            has_range,
            has_multi,
            bool(self.value_email),
            bool(self.value_phone),
        ])

    # -------------------------------------------------
    # Validation
    # -------------------------------------------------

    def clean(self):

        super().clean()

        question = self.question
        t = question.answer_type

        # -----------------------
        # Repeat handling
        # -----------------------

        if not question.is_repeatable and self.repeat_index != 0:
            raise ValidationError(
                "This question does not allow multiple answers"
            )

        # -----------------------
        # Attachments
        # -----------------------

        if question.requires_document:
            if not self.pk or not self.attachments.exists():
                raise ValidationError(
                    "Supporting document required"
                )

        # -----------------------
        # Value existence
        # -----------------------

        has_multi = self.pk and self.selected_options.exists()
        has_value = self.has_value()

        if not question.required and not has_value:
            return

        if question.required and not has_value:
            raise ValidationError(
                "This question requires an answer."
            )

        # -----------------------
        # Type validation
        # -----------------------

        if t == KycQuestion.AnswerTypeEnum.NUMBER:
            if self.value_number is None:
                raise ValidationError("Number answer required")

        elif t == KycQuestion.AnswerTypeEnum.TEXT:
            if not self.value_text:
                raise ValidationError("Text answer required")

        elif t == KycQuestion.AnswerTypeEnum.BOOL:
            if self.value_bool is None:
                raise ValidationError("Boolean answer required")

        # -----------------------
        # SINGLE
        # -----------------------

        elif t == KycQuestion.AnswerTypeEnum.SINGLE:

            if self.value_reference is None:
                raise ValidationError(
                    "Exactly one option must be selected"
                )

            if has_multi:
                raise ValidationError(
                    "Single choice cannot have multiple options"
                )

            # Validate reference set
            if question.reference_set:
                if self.value_reference.reference_set_id != question.reference_set_id:
                    raise ValidationError(
                        "Invalid reference value selected"
                    )

        # -----------------------
        # MULTI
        # -----------------------

        elif t == KycQuestion.AnswerTypeEnum.MULTI:

            if self.value_reference is not None:
                raise ValidationError(
                    "Multi choice cannot use single reference"
                )

            if question.required and not has_multi:
                raise ValidationError(
                    "At least one option must be selected"
                )

            # Validate all selections
            if question.reference_set:
                invalid = self.selected_options.exclude(
                    reference_value__reference_set=question.reference_set
                ).exists()

                if invalid:
                    raise ValidationError(
                        "One or more selected options are invalid"
                    )

        # -----------------------
        # DATE
        # -----------------------

        elif t == KycQuestion.AnswerTypeEnum.DATE:

            if self.value_date is None:
                raise ValidationError("Date required")

        # -----------------------
        # RANGE
        # -----------------------

        elif t == KycQuestion.AnswerTypeEnum.RANGE:

            if not self.value_date_from or not self.value_date_to:
                raise ValidationError("Date range required")

            if self.value_date_from > self.value_date_to:
                raise ValidationError(
                    "Start date must be before end date"
                )

        # -----------------------
        # PHONE
        # -----------------------

        elif t == KycQuestion.AnswerTypeEnum.PHONE:

            if not self.value_phone:
                raise ValidationError("Phone number required")

        # -----------------------
        # EMAIL
        # -----------------------

        elif t == KycQuestion.AnswerTypeEnum.EMAIL:

            if not self.value_email:
                raise ValidationError("Email address required")

        # -------------------------------------------------
        # Group-level validation
        # -------------------------------------------------

        if question.group_id:

            group = (
                KycQuestionGroup.objects
                .prefetch_related("questions")
                .get(pk=question.group_id)
            )

            answers = (
                KycAnswer.objects
                .filter(
                    kyc_record=self.kyc_record,
                    repeat_index=self.repeat_index,
                    question__group=group
                )
                .select_related("question")
            )

            answer_map = {
                a.question_id: a
                for a in answers
            }

            for q in group.questions.all():

                ans = answer_map.get(q.id)

                if q.required and (not ans or not ans.has_value()):
                    raise ValidationError(
                        f"Required question '{q.label}' "
                        f"is missing in repeat {self.repeat_index}"
                    )


# =====================================================
# MULTI SELECT TABLE
# =====================================================

@pghistory.track()
class KycAnswerOption(models.Model):

    answer = models.ForeignKey(
        KycAnswer,
        on_delete=models.CASCADE,
        related_name="selected_options"
    )

    reference_value = models.ForeignKey(
        ReferenceValue,
        on_delete=models.PROTECT,
        related_name="multi_answers",
        null=True,   # temporary
    )

    created_at = models.DateTimeField(default=timezone.now)

    class Meta:

        unique_together = ("answer", "reference_value")

        indexes = [
            models.Index(fields=["answer"]),
            models.Index(fields=["reference_value"]),
        ]

    def __str__(self):
        return f"{self.answer_id} → {self.reference_value.code}"
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