from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver


from watchdog.models import Signal, SignalSeverity, SignalType
import logging

from django.apps import apps
Party = apps.get_model("party", "Party")

@receiver(post_save, sender=Party)
def create_party_signal(sender, instance, created, **kwargs):
    if not created:
        return

    def _create_signal():
        signal_type, _ = SignalType.objects.get_or_create(label="party_created")    # This is core to the system, so it needs to create if it does not exist
        severity = SignalSeverity.objects.get(code="info")  # or whatever default

        Signal.objects.create(
            signal_type=signal_type,
            severity=severity,
            content_object=instance,  # 👈 Generic FK target
            metadata={
                "party_id": str(instance.id),
                "party_type": instance.party_type.code,
                "name": instance.name,
            }
        )

    # Ensure signal is only created after DB commit
    transaction.on_commit(_create_signal)