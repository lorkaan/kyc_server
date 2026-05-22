from django.db import models
from base.models import BaseModel
from watchdog.models import AlertSeverity
from .data_type import EventStatus, TimeMeasurement
import pghistory
from django.utils import timezone
from datetime import timedelta


class AgendaEventType(models.Model):
    
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Human-readable name for the event type, e.g., 'Meeting'."
    )

    code = models.CharField(
        max_length=100,
        unique=True,
        help_text="A code for the internal system to identify the data row without ambiguous spaces"
    )

    description = models.TextField(
        blank=True,
        help_text="Optional description of what this event type represents."
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Agenda Event Type"
        verbose_name_plural = "Agenda Event Types"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return self.name

class AgendaEventTypeAlertSchedule(models.Model):

    event_type = models.ForeignKey(AgendaEventType, on_delete=models.CASCADE, related_name="agenda_event_alert_schedule")

    value = models.IntegerField()

    measurement = models.CharField(max_length=1, choices=TimeMeasurement.choices, default=TimeMeasurement.DAILY)

    severity = models.ForeignKey(AlertSeverity, models.SET_NULL, null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["event_type", "value", "measurement"],
                name="unique_type_value_measurement"
            )
        ]


# Create your models here.
@pghistory.track()
class AgendaEvent(BaseModel):

    title = models.CharField(
        max_length=255
    )

    description = models.TextField(
        blank=True
    )

    event_type = models.ForeignKey(AgendaEventType, on_delete=models.CASCADE, related_name="agenda_events", null=True, blank=True)

    start_time = models.DateTimeField(null=True, blank=True)

    end_time = models.DateTimeField(null=True, blank=True)

    all_day = models.BooleanField(
        default=False
    )

    location = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    organizer = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organized_events"
    )

    status = models.CharField(
        max_length=20,
        choices=EventStatus.choices,
        default=EventStatus.SCHEDULED
    )

    class Meta:
        indexes = [
            models.Index(fields=["start_time"]),
            models.Index(fields=["end_time"]),
            models.Index(fields=["status"]),
            models.Index(fields=["start_time", "end_time"]),
        ]
        ordering = ["start_time"]

    def __str__(self):
        return f"{self.title} ({self.start_time})"

    def clean(self):
        """
        Validate event time range.
        """
        if not self.end_time and not self.start_time:
            raise ValueError("Start Time and End Time can not both be null")
        if self.end_time and self.start_time and self.end_time < self.start_time:
            raise ValueError("end_time must be after start_time")

    @property
    def is_past(self):
        if self.end_time:
            return self.end_time < timezone.now()
        elif self.start_time:
            return self.end_time < timezone.now()
        else:
            return False

    @property
    def is_active(self):
        now = timezone.now()
        if self.end_time and self.start_time:
            return self.start_time <= now <= self.end_time
        elif self.all_day:
            if self.start_time:
                next_day_midnight = (
                    self.start_time.replace(
                        hour=0,
                        minute=0,
                        second=0,
                        microsecond=0
                    ) + timedelta(days=1)
                )
                return self.start_time <= now <= next_day_midnight
            elif self.end_time:
                prev_day_midnight = (
                    self.start_time.replace(
                        hour=0,
                        minute=0,
                        second=0,
                        microsecond=0
                    ) + timedelta(days=1)
                )
                return prev_day_midnight <= now <= self.end_time
            else:
                return False
        else:
            return False
        
    @property
    def normalize_start(self):
        if self.start_time:
            return self.start_time
        elif self.end_time:
            return self.end_time
        else:
            return None
        