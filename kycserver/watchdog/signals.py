from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from watchdog.models import Signal
from automation.tasks import evaluate_signal
import logging

@receiver(post_save, sender=Signal)
def signal_created(sender, instance, created, **kwargs):
    """
    Fire evaluate_signal task after a Signal is saved.
    Ensures task runs only after the DB transaction is committed.
    """
    logger = logging.getLogger()
    logger.error(f"Signal created: {instance.id}")
    if created:
        logger.error(f"Signal evaluating: {instance.id}")
        transaction.on_commit(lambda: evaluate_signal.delay(instance.id))