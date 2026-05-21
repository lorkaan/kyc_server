from django.db import models
import pghistory
from django.utils import timezone
from base.models import BaseModel

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

# Create your models here.
@pghistory.track()
class AgendaEvent(BaseModel):
    
    class EventStatus(models.TextChoices):
        SCHEDULED = "S", "Scheduled"
        CANCELLED = "C", "Cancelled"
        FINISHED = "F", "Finished"

    title = models.CharField(
        max_length=255
    )

    description = models.TextField(
        blank=True
    )

    event_type = models.ForeignKey(AgendaEventType, on_delete=models.CASCADE, related_name="agenda_events", null=True, blank=True)

    start_time = models.DateTimeField()

    end_time = models.DateTimeField()

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
        if self.end_time and self.start_time and self.end_time < self.start_time:
            raise ValueError("end_time must be after start_time")

    @property
    def is_past(self):
        return self.end_time < timezone.now()

    @property
    def is_active(self):
        now = timezone.now()
        return self.start_time <= now <= self.end_time