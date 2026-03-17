from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError

from base.models import BaseModel
from watchdog.models import SignalType
from storedquery.models import SavedQuery

from datetime import timedelta

class AutomationRule(BaseModel):

    name = models.CharField(max_length=255)

    query = models.ForeignKey(
        SavedQuery,
        on_delete=models.CASCADE,
        related_name="automation_rules"
    )

class TriggerTypes(models.TextChoices):
    SIGNAL = "S", "Signal"
    TIME = "T", "Time"


class AutomationTrigger(BaseModel):

    class Schedule(models.TextChoices):
        HOURLY = "H", "Hourly"
        DAILY = "D", "Daily"
        WEEKLY = "W", "Weekly"
        MONTHLY = "M", "Monthly"
        YEARLY = "Y", "Yearly"

    SCHEDULE_DELTAS = {
        Schedule.HOURLY: timedelta(hours=1),
        Schedule.DAILY: timedelta(days=1),
        Schedule.WEEKLY: timedelta(weeks=1),
        Schedule.MONTHLY: timedelta(days=30), # Change this
        Schedule.YEARLY: timedelta(weeks=52)
    }

    schedule = models.CharField(
        max_length=1,
        choices=Schedule.choices,
        null=True,
        blank=True
    )

    trigger_type = models.CharField(max_length=1, choices=TriggerTypes.choices, default=TriggerTypes.TIME)

    signal_type = models.ForeignKey(
        SignalType,
        null=True,
        blank=True,
        on_delete=models.CASCADE
    )

    rule = models.ForeignKey(AutomationRule, on_delete=models.PROTECT, related_name="triggers", null=True, blank=True)

    is_active = models.BooleanField(default=True)

    last_run_at = models.DateTimeField(null=True, blank=True)

    is_running = models.BooleanField(default=False)

    locked_at = models.DateTimeField(null=True, blank=True)

    name = models.CharField(max_length=255, null=True, blank=True)

    def clean(self):
        if self.trigger_type == TriggerTypes.SIGNAL and not self.signal_type:
            raise ValidationError("Signal trigger requires signal_type")

        if self.trigger_type == TriggerTypes.TIME and not self.schedule:
            raise ValidationError("Schedule trigger requires to be assigned a schedule")
        
    def should_run(self):

        if not self.last_run_at:
            return True

        delta = timezone.now() - self.last_run_at

        return delta >= self.SCHEDULE_DELTAS.get(
            self.schedule,
            timedelta.max
        )
        
    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(trigger_type=TriggerTypes.SIGNAL, signal_type__isnull=False, schedule__isnull=True) |
                    models.Q(trigger_type=TriggerTypes.TIME, signal_type__isnull=True, schedule__isnull=False)
                ),
                name="valid_trigger_configuration"
            ),
            models.UniqueConstraint(
                fields=['name'],
                condition=models.Q(name__isnull=False),
                name="unique_non_null_name"
            )
        ]
        indexes = [
            models.Index(fields=["trigger_type", "signal_type"]),
            models.Index(fields=["trigger_type", "schedule"]),
        ]

# Create your models here.
class AutomationAction(BaseModel):

    trigger = models.ForeignKey(AutomationTrigger, on_delete=models.PROTECT, related_name="actions", null=True, blank=True)

    # BooleanLogicEngine-compatible JSON
    condition = models.JSONField(null=True, blank=True)

    type = models.CharField(
        max_length=255,
        help_text="The action type registered in ActionRunner",
    )

    config = models.JSONField(default=dict)

    order = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)

    def clean(self):
        if self.is_active and not self.trigger:
            raise ValidationError(
                "Active actions must be attached to a trigger"
            )
        
    class Meta:
        ordering = ['order']

class RunModel(BaseModel):
    class RunStatus(models.TextChoices):
        PENDING = "P", "Pending"
        RUNNING = "R", "Running"
        COMPLETED = "C", "Completed"
        FAILED = "F", "Failed"

    status = models.CharField(
        max_length=1,
        choices=RunStatus.choices,
        default=RunStatus.PENDING
    )

    class Meta:
        abstract = True

class AutomationRun(RunModel):

    trigger = models.ForeignKey(
        AutomationTrigger,
        on_delete=models.CASCADE,
        related_name="runs"
    )

    rule = models.ForeignKey(
        AutomationRule,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    context = models.JSONField(default=dict, blank=True)

    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    error = models.TextField(null=True, blank=True)

class AutomationActionRun(RunModel):

    run = models.ForeignKey(
        AutomationRun,
        on_delete=models.CASCADE,
        related_name="action_runs"
    )

    action = models.ForeignKey(
        AutomationAction,
        on_delete=models.CASCADE
    )

    error = models.TextField(null=True, blank=True)