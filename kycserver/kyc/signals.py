# kyc/signals.py
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import KYCRecord, KYCStatus, RiskScore
from django.conf import settings
from party.models import Party
import logging
import redis
"""
redis_client = redis.Redis.from_url(settings.REDIS_URL)

@receiver(post_save, sender=KYCRecord)
def publish_kyc_record(sender, instance, created, **kwargs):
    if not created:
        return

    #user_id = instance.party.owner_id  # assumes Party has owner field
    channel = f"kyc_user_{user_id}"

    data = {
        "id": instance.id,
        "party_id": instance.party_id,
        "status": instance.status.code,
        "created_at": instance.created_at.isoformat(),
    }
    redis_client.publish(channel, json.dumps(data))
"""

_DEFAULT_RISK_SCORE = 1
_INITIAL_KYC_RECORD_STATUS = "created"

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
                risk_score= RiskScore.create(score=_DEFAULT_RISK_SCORE)
            )
            record.save()
        except KYCStatus.DoesNotExist:
            # log it, fallback, or raise a controlled error
            logger = logging.getLogger(__name__)
            logger.error(f"KYCStatus {_INITIAL_KYC_RECORD_STATUS} not found. Cannot create KYCRecord for Party {instance.id}")

    transaction.on_commit(_create_kyc)