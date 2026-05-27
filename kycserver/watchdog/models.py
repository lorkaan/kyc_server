from django.utils import timezone

from django.db import models

import pghistory
from base.models import BaseModel, GenericTargetMixin, NullableGenericTargetMixin

class AlertStatus(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=50)
    is_terminal = models.BooleanField(default=False)

    def __str__(self):
        return self.name

class AlertSeverity(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=50)
    rank = models.PositiveSmallIntegerField()  # sorting / escalation

    def __str__(self):
        return self.name

class AlertReason(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)

    # Defaults (can be overridden per alert)
    default_severity = models.ForeignKey(
        "AlertSeverity",
        on_delete=models.PROTECT,
        related_name="default_for_reasons",
    )

    def __str__(self):
        return f"{self.code} – {self.name}"

@pghistory.track()
class Alert(BaseModel, GenericTargetMixin):
    reason = models.ForeignKey(AlertReason, on_delete=models.PROTECT)
    severity = models.ForeignKey(AlertSeverity, on_delete=models.PROTECT)
    status = models.ForeignKey(AlertStatus, on_delete=models.PROTECT)
    message = models.TextField()
    triggered_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["triggered_at", "-severity"]

class SignalSeverity(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=50)
    rank = models.PositiveSmallIntegerField()  # sorting / escalation

    def __str__(self):
        return self.name
    
class SignalType(models.Model):
    label = models.CharField(max_length=50)

@pghistory.track()
class Signal(BaseModel, NullableGenericTargetMixin):
    signal_type = models.ForeignKey(SignalType, on_delete=models.PROTECT)
    severity = models.ForeignKey(SignalSeverity, on_delete=models.PROTECT)
    metadata = models.JSONField(default=dict, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)

