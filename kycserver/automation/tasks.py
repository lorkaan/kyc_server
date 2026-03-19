from celery import shared_task
from django.db import transaction, OperationalError
from django.utils import timezone
from watchdog.models import Signal
from .models import AutomationTrigger, AutomationActionRun, AutomationRun, TriggerTypes
from utils.queryAstHandler import QueryAstHandler
from utils.action_runner import ActionRunner
from utils.boolAstHandler import BooleanAstHandler  # Your Boolean DSL evaluator
from datetime import timedelta

import logging

logger = logging.getLogger()

LOCK_TIMEOUT = timedelta(minutes=30)

# -----------------------------
# Signal-triggered automation
# -----------------------------
@shared_task
def evaluate_signal(signal_id):
    """
    Called when a signal occurs.
    Finds all active triggers for this signal and runs them.
    """
    signal = Signal.objects.get(id=signal_id)
    triggers = AutomationTrigger.objects.filter(
        is_active=True,
        trigger_type=TriggerTypes.SIGNAL,
        signal_type=signal.signal_type
    )
    logger.error(f"Evaluating signal id: {signal_id}, which corresponds to {signal}")
    for trigger in triggers:
        run_trigger.delay(trigger.id, signal_id=signal.id)


# -----------------------------
# Scheduled automation
# -----------------------------
@shared_task
def run_due_triggers():
    """
    Finds all active scheduled triggers that are due and runs them.
    """
    triggers = AutomationTrigger.objects.filter(
        is_active=True,
        trigger_type=TriggerTypes.TIME
    )
    for trigger in triggers:
        if trigger.should_run():
            run_trigger.delay(trigger.id)


# -----------------------------
# Thread-safe trigger runner
# -----------------------------
@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def run_trigger(self, trigger_id, signal_id=None):
    now = timezone.now()
    logger.error(f"Running Trigger: {trigger_id}")
    try:
        # Acquire a lock safely
        with transaction.atomic():
            try:
                trigger = (
                    AutomationTrigger.objects
                    .select_for_update(nowait=True)
                    .get(id=trigger_id, is_active=True)
                )
            except OperationalError:
                # Row is locked by another worker → skip
                return

            # Skip if a fresh lock exists
            if trigger.is_running and trigger.locked_at and now - trigger.locked_at < LOCK_TIMEOUT:
                logger.error(f"Trigger: {trigger_id} is locked")
                return

            # Recover stale lock
            trigger.is_running = True
            trigger.locked_at = now
            trigger.save(update_fields=["is_running", "locked_at"])

        # ------------------------------
        # Run actions outside DB lock
        # ------------------------------
        results = None
        if trigger.rule:
            results = QueryAstHandler.run(
                trigger.rule.query.query_def,
                trigger.rule.query.params or {}
            )

        context = {
            "trigger_id": trigger.id,
            "signal_id": signal_id,
            "task_id": self.request.id,
            "started_at": now,
        }

        run = AutomationRun.objects.create(
            trigger=trigger,
            rule=trigger.rule,
            context=results or {},
            started_at=now,
            status=AutomationRun.RunStatus.RUNNING,
        )

        logger.error(f"Excuting Actions")

        # Execute actions
        for action in trigger.actions.filter(is_active=True).order_by("order"):
            logger.error(f"\tExcuting Action: {action}")
            should_run = True
            if action.condition:
                should_run = BooleanAstHandler.run(
                    action.condition, results or {}
                )

            if should_run:
                try:
                    ActionRunner.run(action, results, context)
                    AutomationActionRun.objects.create(
                        run=run, action=action,
                        status=AutomationActionRun.RunStatus.COMPLETED
                    )
                except Exception as e:
                    AutomationActionRun.objects.create(
                        run=run, action=action,
                        status=AutomationActionRun.RunStatus.FAILED,
                        error=str(e)
                    )

        # ------------------------------
        # Release lock & mark completion
        # ------------------------------
        with transaction.atomic():
            trigger = AutomationTrigger.objects.select_for_update().get(id=trigger.id)
            trigger.last_run_at = timezone.now()
            trigger.is_running = False
            trigger.locked_at = None
            trigger.save(update_fields=["last_run_at", "is_running", "locked_at"])

            run.finished_at = timezone.now()
            run.status = AutomationRun.RunStatus.COMPLETED
            run.save(update_fields=["finished_at", "status"])

    except OperationalError as exc:
        raise self.retry(exc=exc)
    except Exception as exc:
        AutomationTrigger.objects.filter(id=trigger_id).update(is_running=False, locked_at=None)
        raise self.retry(exc=exc)
