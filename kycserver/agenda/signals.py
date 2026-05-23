from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta

from automation.actions import create_alert
from watchdog.models import AlertReason, AlertStatus
from .data_type import TimeMeasurement

from .models import AgendaEvent, AgendaEventTypeAlertSchedule

SCHEDULE_DELTAS = {
    TimeMeasurement.HOURLY: timedelta(hours=1),
    TimeMeasurement.DAILY: timedelta(days=1),
    TimeMeasurement.WEEKLY: timedelta(weeks=1),
    TimeMeasurement.MONTHLY: timedelta(days=30), # Change this
    TimeMeasurement.YEARLY: timedelta(weeks=52)
}

def calculate_time_diff(ref_datetime, value, measurement):
    return ref_datetime - (value * SCHEDULE_DELTAS.get(measurement, timedelta(days=1)))

@receiver(post_save, sender=AgendaEvent)
def create_alerts_for_event(sender, instance, created, **kwargs):
    if not created:
        return

    def _create_alerts():
        try:
            alert_reason = AlertReason.objects.get(code="EVENT")
            try:
                alert_status = AlertStatus.objects.get(code="open")
                e_type = instance.event_type
                reference_start = instance.normalize_start
                schedule = list(AgendaEventTypeAlertSchedule.objects.filter(event_type=e_type).values("value", "measurement"))
                for sched_obj in schedule:
                    cur_val = sched_obj.get("value", 0)
                    cur_measurement = sched_obj.get("measurement", None)
                    if cur_measurement == None:
                        continue
                    else:
                        triggered_time = calculate_time_diff(reference_start, cur_val, cur_measurement)
                        if triggered_time < timezone.now():
                            continue
                        else:
                            create_alert(instance.title, alert_reason, alert_status, instance.severity if instance.severity else alert_reason.default_severity, instance, triggered_time)
            except AlertStatus.DoesNotExist as e:
                import logging
                logger = logging.getLogger()
                logger.error(f"Can not find the Open Alert Status: {e}")
        except AlertReason.DoesNotExist as e:
            import logging
            logger = logging.getLogger()
            logger.error(f"Can not find the Event Alert Reason: {e}")
        except Exception as e:
            import logging
            logger = logging.getLogger()
            logger.error(f"Unknown Error occured: {e}")

    #transaction.on_commit(_create_alerts)
    _create_alerts()