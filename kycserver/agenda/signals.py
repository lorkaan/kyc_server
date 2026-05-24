from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
import logging

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
    signal_logger = logging.getLogger()
    signal_logger.error(f"Signal to create Alert made: \n\tInstance: {instance} \n\tCreated: {created}")
    if not created:
        signal_logger.error(f"Can not run: {created}")
        return
    def _create_alerts():
        try:
            alert_reason = AlertReason.objects.get(code="EVENT")
            try:
                alert_status = AlertStatus.objects.get(code="open")
                e_type = instance.event_type
                reference_start = instance.normalize_start
                schedule = list(AgendaEventTypeAlertSchedule.objects.filter(event_type=e_type).values("value", "measurement", "severity"))
                signal_logger.error(f"Schedule: {schedule}")
                for sched_obj in schedule:
                    cur_val = sched_obj.get("value", 0)
                    cur_measurement = sched_obj.get("measurement", None)
                    cur_severity = sched_obj.get("severity", None)
                    if cur_measurement == None:
                        continue
                    else:
                        triggered_time = calculate_time_diff(reference_start, cur_val, cur_measurement)
                        now_time = timezone.now()
                        if triggered_time < now_time:
                            signal_logger.error(f"Triggered time is less than now time: {triggered_time} < {now_time}")
                            continue
                        else:
                            create_alert(instance.title, alert_reason, alert_status, cur_severity if cur_severity else alert_reason.default_severity, instance, triggered_time)
            except AlertStatus.DoesNotExist as e:  
                logger = logging.getLogger()
                logger.error(f"Can not find the Open Alert Status: {e}")
        except AlertReason.DoesNotExist as e:
            logger = logging.getLogger()
            logger.error(f"Can not find the Event Alert Reason: {e}")
        except Exception as e:
            logger = logging.getLogger()
            logger.error(f"Unknown Error occured: {e}")

    transaction.on_commit(_create_alerts)
    #_create_alerts()