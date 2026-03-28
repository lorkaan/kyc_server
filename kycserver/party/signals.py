from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from kyc.models import KYCRecord, KYCStatus
from party.models import Party
from watchdog.models import Signal, SignalSeverity, SignalType
from kyc.models import KYCRecord, KYCStatus
import logging

_DEFAULT_RISK_SCORE = 1
_INITIAL_KYC_RECORD_STATUS = "created"

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
                "party_id": instance.id,
                "party_type": instance.party_type.code,
                "name": instance.name,
            }
        )

    # Ensure signal is only created after DB commit
    transaction.on_commit(_create_signal)

@receiver(post_save, sender=Party)
def create_kyc_record(sender, instance, created, **kwargs):
    if not created:
        return

    def _create_kyc():
        try:
            status = KYCStatus.objects.get(code=_INITIAL_KYC_RECORD_STATUS)
            record = KYCRecord(
                party=instance,
                status=status,
                risk=_DEFAULT_RISK_SCORE
            )
            record.save()
        except KYCStatus.DoesNotExist:
            # log it, fallback, or raise a controlled error
            logger = logging.getLogger(__name__)
            logger.error(f"KYCStatus {_INITIAL_KYC_RECORD_STATUS} not found. Cannot create KYCRecord for Party {instance.id}")

    transaction.on_commit(_create_kyc)