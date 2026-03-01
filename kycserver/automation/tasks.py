from celery import shared_task
from django.db import transaction, OperationalError
from django.utils import timezone

from .models import AutomationRule
from utils.queryAstHandler import QueryAstHandler
from utils.action_runner import ActionRunner

from datetime import timedelta


LOCK_TIMEOUT = timedelta(minutes=30)


@shared_task(bind=True, max_retries=5, default_retry_delay=60)
def run_automation_rule(self, rule_id):

    now = timezone.now()

    try:
        with transaction.atomic():

            rule = (
                AutomationRule.objects
                .select_for_update()
                .get(id=rule_id, is_active=True)
            )

            # ----------------------------------
            # Crash recovery logic
            # ----------------------------------

            if rule.is_running:

                # If lock is still fresh → skip
                if rule.locked_at and now - rule.locked_at < LOCK_TIMEOUT:
                    return

                # Otherwise → stale lock → recover
                # (previous worker died)
                rule.is_running = False
                rule.locked_at = None


            # Normal schedule check
            if not rule.should_run():
                return


            # Acquire lease
            rule.is_running = True
            rule.locked_at = now
            rule.save(update_fields=["is_running", "locked_at"])


        # ------------------------------
        # Run OUTSIDE transaction
        # ------------------------------
        # Important: do NOT hold DB lock while running actions

        query = rule.query

        results = QueryAstHandler.run(
            query.query_def,
            query.params or {}
        )

        context = {
            "rule_id": rule.id,
            "task_id": self.request.id,
            "started_at": now,
        }

        actions = rule.actions.filter(is_active=True).order_by("order")

        for action in actions:
            ActionRunner.run(action, results, context)


        # ------------------------------
        # Mark success
        # ------------------------------

        with transaction.atomic():

            rule = AutomationRule.objects.select_for_update().get(id=rule.id)

            rule.last_run_at = timezone.now()
            rule.is_running = False
            rule.locked_at = None

            rule.save(
                update_fields=["last_run_at", "is_running", "locked_at"]
            )


    except OperationalError as exc:
        raise self.retry(exc=exc)

    except Exception as exc:

        # Release lock on failure
        AutomationRule.objects.filter(id=rule_id).update(
            is_running=False,
            locked_at=None
        )

        raise self.retry(exc=exc)


@shared_task
def check_and_run_automation_rules():
    """
    Dispatches due automation rules
    """

    rules = AutomationRule.objects.filter(is_active=True)

    for rule in rules:
        if rule.should_run():
            run_automation_rule.delay(rule.id)