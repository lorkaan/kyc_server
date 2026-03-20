
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

@ActionRunner.register("create_alert")
def create_alert_action(results, config, context):
    title = config.get("title", "Default Alert")

    signal_type_obj = getSignalTypeIdFromSignalId(context.get("signal", None))
    if signal_type_obj != None:
        alert_message = f"{title} - {signal_type_obj.label}"
        try:
            alert_obj = Alert.objects.create(message=alert_message, reason__pk=1, status__pk=1, severity__pk=1)
            alert_obj.save()
        except Exception as e:
            logger.error(f"Alert Object Issue: {e}")
    else:
        logger.error(f"Signal Type could not be found")