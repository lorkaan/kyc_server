
import logging
from kyc.models import KYCRecord, KYCStatus, RiskScore
from globalparams.actions import getGlobalParamByName
from agenda.models import AgendaEvent, AgendaEventType
from base.models import ModelSchemaMixin
from party.models import Party
from users.models import User
from utils.type_utils import isNumber, isString
from watchdog.generate_signals import create_signal
from watchdog.models import Alert, AlertReason, AlertSeverity, AlertStatus, Signal, SignalType
from utils.action_runner import ActionRunner
from django.utils import timezone
from django.utils.dateparse import parse_datetime, parse_date
from datetime import datetime, time

logger = logging.getLogger(__name__)

verify_signal_name = "verify_kyc_record"
verified_signal_name = "verified_kyc_record"
manual_verify_signal_name = "manual_verify_required_kyc_record"

new_risk_score_signal_name = "new_risk_score_created"
global_risk_score_threshold_key = "risk_score_threshold"
_default_global_risk_score_threshold_value = 5



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
        

def normalize_datetime(value):
    if value is None:
        return None

    # Already a datetime
    if isinstance(value, datetime):
        return value

    # Try full datetime string
    dt = parse_datetime(value)
    if dt:
        return dt

    # Try date-only string
    d = parse_date(value)
    if d:
        # Convert date → datetime (midnight)
        return datetime.combine(d, time.min)

    raise ValueError("Invalid datetime/date format for triggered_at")

@ActionRunner.register("create_expiry_event")
def create_expiry_event_action(results, config, context):
    signal_obj = getSignal(context.get("signal_id", None))
    if signal_obj != None:
        target = signal_obj.content_object
        if isinstance(target, KYCRecord) and target.expiry_date != None:
            try:
                event_type = AgendaEventType.objects.get(code="kyc_record_expiry")
            except KYCStatus.DoesNotExist as e:
                logger.error(f"Can not get status pending for signal: {signal_obj.pk}")
                event_type=None
            finally:
                expiry_date = target.expiry_date
                if isinstance(target.party, Party):
                    if len(target.party.name) > 0:
                        event_title = f"KYC Expired for Party: {str(target.party.name)}"
                    elif isinstance(target.party.content_object, ModelSchemaMixin):
                        event_title = f"KYC Expired for Party: {str(target.party.content_object.name)}"
                    else:
                        event_title = f"KYC Expired for Party: {str(target.party.id)}"
                else:
                    event_title = f"KYC Expired - {str(target.id)}"
                try:
                    event_obj = AgendaEvent.objects.create(title=event_title, event_type=event_type, start_time=expiry_date)
                    event_obj.save()
                except Exception as e:
                    logger.error(f"Error saving event: {e}")
                return
        else:
            return
    else:
        return
        
def create_alert(message, reason=None, status=None, severity=None, obj=None, triggered_at=None):

    def resolve_fk(value, model):
        if value is None:
            raise ValueError(f"{model.__name__} is required")
        if isinstance(value, model):
            return value
        return model.objects.get(pk=value)

    if obj is None:
        raise ValueError("create_alert requires 'obj' (target object)")

    try:
        try:
            normalized_triggered_at = normalize_datetime(triggered_at)
        except ValueError:
            normalized_triggered_at = None
        finally:
            if normalized_triggered_at == None:
                alert_obj = Alert(
                    message=message,
                    reason=resolve_fk(reason, AlertReason),
                    status=resolve_fk(status, AlertStatus),
                    severity=resolve_fk(severity, AlertSeverity),
                )
            else:
                alert_obj = Alert(
                    message=message,
                    reason=resolve_fk(reason, AlertReason),
                    status=resolve_fk(status, AlertStatus),
                    severity=resolve_fk(severity, AlertSeverity),
                    triggered_at=normalized_triggered_at
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

    
@ActionRunner.register("kyc_submitted")
def kyc_submitted(results, config, context):
    signal_obj = getSignal(context.get("signal_id", None))
    if signal_obj != None:
        target = signal_obj.content_object
        if isinstance(target, KYCRecord):
            try:
                kyc_status = KYCStatus.objects.get(code="pending")
                target.status = kyc_status
                target.save()
            except KYCStatus.DoesNotExist as e:
                logger.error(f"Can not get status pending for signal: {signal_obj.pk}")
            return
        else:
            return
    else:
        return
    
@ActionRunner.register("decline_verification_kyc")
def decline_verification_kyc(results, config, context):
    signal_obj = getSignal(context.get("signal_id", None))
    if signal_obj != None:
        target = signal_obj.content_object
        if isinstance(target, KYCRecord):
            try:
                kyc_status = KYCStatus.objects.get(code="rejected")
                target.status = kyc_status
                target.save()
            except KYCStatus.DoesNotExist as e:
                logger.error(f"Can not get status rejected for signal: {signal_obj.pk}")
            return
        else:
            return
    else:
        return

@ActionRunner.register("manual_verify_kyc")
def manually_verify_record(results, config, context):
    signal_obj = getSignal(context.get("signal_id", None))
    if signal_obj != None:
        target = signal_obj.content_object
        if isinstance(target, KYCRecord):
            user_id = signal_obj.metadata.get("user_id", None)
            if user_id != None:
                try:
                    user = User.objects.get(pk=user_id)
                    try:
                        kyc_status = KYCStatus.objects.get(code="approved")
                        target.status = kyc_status
                        target.verify_manual(user)
                    except KYCStatus.DoesNotExist as e:
                        logger.error(f"Can not get status pending for signal: {signal_obj.pk}")
                except User.DoesNotExist as e:
                    logger.error(f"Can not find user for id: {user_id}")
                return
            else:
                return
        else:
            return
    else:
        return
    
def check_risk_score(risk_score_value):
    if isNumber(risk_score_value, lambda x: x > 0):
        from globalparams.models import GlobalParameter
        try:
            global_param = GlobalParameter.objects.get(name=global_risk_score_threshold_key)
            global_val = global_param.get_value()
            if isNumber(global_val) and global_val >= 0:
                return global_val > risk_score_value
            else:
                return _default_global_risk_score_threshold_value > risk_score_value
        except GlobalParameter.DoesNotExist as e:
            import logging
            logger = logging.getLogger()
            logger.error(e)
            return _default_global_risk_score_threshold_value > risk_score_value
    else:
        return False
    
@ActionRunner.register("risk_score_update")
def risk_score_updated_for_record(results, config, context):
    signal_obj = getSignal(context.get("signal_id", None))
    if signal_obj != None:
        target = signal_obj.content_object
        if isinstance(target, RiskScore):
            record = target.kyc_record
            auto_check = check_risk_score(target.score)
            if auto_check:
                try:
                    kyc_status = KYCStatus.objects.get(code="approved")
                    record.status = kyc_status
                    record.verify_system()
                except KYCStatus.DoesNotExist as e:
                    logger.error(f"Can not get status pending for signal: {signal_obj.pk}")
                return
            else:
                try:
                    kyc_status = KYCStatus.objects.get(code="under_review")
                    record.status = kyc_status
                    record.save()
                except KYCStatus.DoesNotExist as e:
                    logger.error(f"Can not get status pending for signal: {signal_obj.pk}")
                return
        else:
            return
    else:
        return
    