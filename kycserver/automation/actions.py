
import logging
from watchdog.models import Alert, AlertReason, AlertSeverity, AlertStatus, Signal, SignalType
from utils.action_runner import ActionRunner

logger = logging.getLogger(__name__)

def getSignal(signal_id):
    if signal_id == None:
        return None
    else:
        try:
            return Signal.objects.get(pk=signal_id)
        except Signal.DoesNotExist as e:
            return None
        except Exception as e:
            return None
        
def create_alert(message, reason=None, status=None, severity=None, obj=None):

    def resolve_fk(value, model):
        if value is None:
            raise ValueError(f"{model.__name__} is required")
        if isinstance(value, model):
            return value
        return model.objects.get(pk=value)

    if obj is None:
        raise ValueError("create_alert requires 'obj' (target object)")

    try:
        alert_obj = Alert(
            message=message,
            reason=resolve_fk(reason, AlertReason),
            status=resolve_fk(status, AlertStatus),
            severity=resolve_fk(severity, AlertSeverity),
        )

        # ✅ Properly set GenericForeignKey
        alert_obj.set_target(obj)

        alert_obj.save()
        return alert_obj

    except Exception as e:
        raise ValueError(f"Failed to create alert: {e}")

@ActionRunner.register("create_alert")
def create_alert_action(results, config, context):
    title = config.get("title", "Default Alert")
    signal_obj = getSignal(context.get("signal_id", None))
    if signal_obj != None:
        alert_message = f"{title} - {signal_obj.signal_type.label}"
        try:
            create_alert(alert_message, reason=1, status=1, severity=1, obj=signal_obj.content_object)
        except Exception as e:
            logger.error(f"Alert Object Issue: {e}")
    else:
        logger.error(f"Signal Type could not be found")