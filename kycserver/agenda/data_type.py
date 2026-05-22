from django.db import models


class TimeMeasurement(models.TextChoices):
        HOURLY = "H", "Hourly"
        DAILY = "D", "Daily"
        WEEKLY = "W", "Weekly"
        MONTHLY = "M", "Monthly"
        YEARLY = "Y", "Yearly"

class EventStatus(models.TextChoices):
        SCHEDULED = "S", "Scheduled"
        CANCELLED = "C", "Cancelled"
        FINISHED = "F", "Finished"