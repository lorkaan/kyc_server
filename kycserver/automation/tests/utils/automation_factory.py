from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from watchdog.models import Signal, SignalType
from automation.models import AutomationTrigger, AutomationAction, TriggerTypes
from automation.tasks import evaluate_signal


class AutomationTestFactory:

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
    def emit_signal(signal_type, obj=None, payload=None):
        """
        Emits a Signal for a model instance.
        """
        signal_type_obj = AutomationTestFactory.signal_type(signal_type)

        content_type = None
        object_id = None

        if obj:
            content_type = ContentType.objects.get_for_model(obj)
            object_id = obj.pk

        signal = Signal.objects.create(
            signal_type=signal_type_obj,
            content_type=content_type,
            object_id=object_id,
            payload=payload or {},
            created_at=timezone.now()
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
    def alert_created():
        """
        Helper for create_alert action tests.
        Adjust if your alert model differs.
        """
        return Signal.objects.filter(
            signal_type__name="create_alert"
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
