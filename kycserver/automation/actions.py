
import logging
from watchdog.models import Alert, SignalType
from utils.action_runner import ActionRunner

logger = logging.getLogger(__name__)

@ActionRunner.register("create_alert")
def create_alert_action(results, config, context):
    title = config.get("title", "Default Alert")
    signal_type_id = config.get("signal_type_id")
    logger.error(f"Title: {title}\n\tSignal Type: {signal_type_id}\n\n\tContext: {context}\n\n\tResults: {results}")
    try:
        signal_type_obj = SignalType.objects.get(pk=signal_type_id)
        alert_message = f"{title} - {signal_type_obj.label}"
        try:
            alert_obj = Alert.objects.create(message=alert_message, reason__pk=1, status__pk=1, severity__pk=1)
            alert_obj.save()
        except Exception as e:
            logger.error(f"Alert Object Issue: {e}")
    except SignalType.DoesNotExist as e:
        logger.error(f"Signal Type could not be found: ID -> {signal_type_id}\n\t{e}")
    except Exception as e:
        logger.error(f"Action Runner Exception: {e}")