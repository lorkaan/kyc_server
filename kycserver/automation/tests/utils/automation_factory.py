from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from watchdog.models import Alert, Signal, SignalSeverity, SignalType
from automation.models import AutomationTrigger, AutomationAction, TriggerTypes
from automation.tasks import evaluate_signal


class AutomationTestFactory:

    default_signal_severity_code = "low"

    default_signal_severity_rank = 10

    @staticmethod
    def signal_type(name):
        signal_type, _ = SignalType.objects.get_or_create(label=name)
        return signal_type

    @staticmethod
    def signal_trigger(signal_type, action_type, config=None):
        """
        Creates:
        SignalType -> AutomationTrigger -> AutomationAction
        """
        signal_type_obj = AutomationTestFactory.signal_type(signal_type)

        trigger = AutomationTrigger.objects.create(
            trigger_type=TriggerTypes.SIGNAL,
            signal_type=signal_type_obj,
            is_active=True
        )

        action = AutomationAction.objects.create(
            trigger=trigger,
            type=action_type,
            config=config or {},
            order=1,
            is_active=True
        )

        return trigger, action

    @staticmethod
    def emit_signal(signal_type, obj=None, payload=None, severity_code=None, severity_rank=None):
        """
        Emits a Signal for a model instance.
        """
        signal_type_obj = AutomationTestFactory.signal_type(signal_type)

        content_type = None
        object_id = None

        if obj:
            content_type = ContentType.objects.get_for_model(obj)
            object_id = obj.pk

        if severity_code == None:
            severity_code = AutomationTestFactory.default_signal_severity_code
        if severity_rank == None:
            severity_rank = AutomationTestFactory.default_signal_severity_rank

        serverity, _ = SignalSeverity.objects.get_or_create(
            code=severity_code,
            rank=severity_rank
        )

        signal = Signal.objects.create(
            signal_type=signal_type_obj,
            content_type=content_type,
            object_id=object_id,
            metadata=payload or {},
            severity=serverity
        )

        return signal

    @staticmethod
    def run_signal(signal):
        """
        Runs the evaluate_signal task synchronously.
        """
        evaluate_signal(signal.id)

    @staticmethod
    def run_trigger(trigger):
        """
        Runs a trigger directly (bypasses signal creation).
        """
        from automation.tasks import run_trigger
        run_trigger(trigger.id)

    @staticmethod
    def signal_created(label):
        """
        Helper for create_alert action tests.
        Adjust if your alert model differs.
        """
        return Signal.objects.filter(
            signal_type__label=label
        ).exists()

    @staticmethod
    def alert_created(reason):
        """
        Helper for create_alert action tests.
        Adjust if your alert model differs.
        """
        return Alert.objects.filter(
            reason__name=reason
        ).exists()

    @staticmethod
    def schedule_trigger(schedule, action_type, config=None):
        trigger = AutomationTrigger.objects.create(
            trigger_type=TriggerTypes.TIME,
            schedule=schedule,
            is_active=True
        )

        action = AutomationAction.objects.create(
            trigger=trigger,
            type=action_type,
            config=config or {},
            order=1,
            is_active=True
        )

        return trigger, action
