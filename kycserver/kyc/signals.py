# kyc/signals.py
import json
from django.db.models.signals import post_save
from django.dispatch import receiver
from kyc.models import KYCRecord
from django.conf import settings
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