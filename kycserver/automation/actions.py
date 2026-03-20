
import logging
from watchdog.models import Alert, Signal, SignalType
from utils.action_runner import ActionRunner

logger = logging.getLogger(__name__)

def getSignalTypeIdFromSignalId(signal_id):
    logger.error(f"Starting Get Signal Type from ID: {signal_id}")
    if signal_id == None:
        return None
    else:
        logger.error(f"Getting Signal Type from ID: {signal_id}")
        try:
            signal = Signal.objects.get(pk=signal_id)
            logger.error(f"Signal: {signal} Type: {signal.signal_type}")
            return signal.signal_type
        except Signal.DoesNotExist as e:
            logger.error(f"Signal ID could not be found on a signal: {signal_id}")
            return None
        except Exception as e:
            logger.error(f"Action Runner Exception: {e}")
            return None
        
def create_alert(message, reason=None, status=None, severity=None):
    def resolve_fk(value, model):
        if value is None:
            return None
        if isinstance(value, model):
            return value
        return model.objects.get(pk=value)

    from .models import Alert, Reason, Status, Severity  # adjust import as needed

    try:
        alert_obj = Alert.objects.create(
            message=message,
            reason=resolve_fk(reason, Reason),
            status=resolve_fk(status, Status),
            severity=resolve_fk(severity, Severity),
        )
        return alert_obj
    except Exception as e:
        # Optional: log or re-raise with clearer context
        raise ValueError(f"Failed to create alert: {e}")

@ActionRunner.register("create_alert")
def create_alert_action(results, config, context):
    title = config.get("title", "Default Alert")
    logger.error(f"\tContext: {context}")
    signal_type_obj = getSignalTypeIdFromSignalId(context.get("signal_id", None))
    if signal_type_obj != None:
        alert_message = f"{title} - {signal_type_obj.label}"
        try:
            create_alert(alert_message, reason=1, status=1, severity=1)
        except Exception as e:
            logger.error(f"Alert Object Issue: {e}")
    else:
        logger.error(f"Signal Type could not be found")