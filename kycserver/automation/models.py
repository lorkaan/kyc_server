from django.db import models

from base.models import BaseModel
from storedquery.models import SavedQuery

from datetime import timedelta
from django.utils import timezone

class AutomationRule(BaseModel):

    class Schedule(models.TextChoices):
        HOURLY = "hourly", "Hourly"
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"

    SCHEDULE_DELTAS = {
        Schedule.HOURLY: timedelta(hours=1),
        Schedule.DAILY: timedelta(days=1),
        Schedule.WEEKLY: timedelta(weeks=1),
        Schedule.MONTHLY: timedelta(days=30),
    }

    name = models.CharField(max_length=255)

    query = models.ForeignKey(
        SavedQuery,
        on_delete=models.CASCADE,
        related_name="automation_rules"
    )

    is_active = models.BooleanField(default=True)

    schedule = models.CharField(
        max_length=1,
        choices=Schedule.choices,
        default=Schedule.DAILY,
    )

    last_run_at = models.DateTimeField(null=True, blank=True)

    is_running = models.BooleanField(default=False)

    locked_at = models.DateTimeField(null=True, blank=True)

    def should_run(self):

        if not self.last_run_at:
            return True

        delta = timezone.now() - self.last_run_at

        return delta >= self.SCHEDULE_DELTAS.get(
            self.schedule,
            timedelta.max
        )

# Create your models here.
class AutomationAction(BaseModel):

    rule = models.ForeignKey(
        AutomationRule,
        on_delete=models.CASCADE,
        related_name="actions"
    )

    type = models.CharField(max_length=50)

    config = models.JSONField(default=dict)

    order = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)