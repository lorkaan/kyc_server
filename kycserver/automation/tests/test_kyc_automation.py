from django.test import TestCase
import uuid

from kyc.models import KYCRecord, KYCStatus
from automation.tests.utils.automation_factory import AutomationTestFactory
from automation.models import AutomationTrigger
from person.models import Person
from party.models import Party, PartyType

from django.contrib.contenttypes.models import ContentType
from datetime import date
from kycserver.settings import CELERY_TASK_ALWAYS_EAGER, CELERY_TASK_EAGER_PROPAGATES
import logging
import time

class KycAutomationTests(TestCase):

    logger = logging.getLogger()

    def test_kyc_creation_creates_alert(self):

        self.assertEqual(AutomationTestFactory.count_alerts(), 0)
        self.assertEqual(AutomationTestFactory.count_signals(), 0)

        person, _ = Person.objects.get_or_create(
            first_name="Test",
            last_name="Customer",
            date_of_birth=date(1990, 1, 1)
        )

        party_type, _ = PartyType.objects.get_or_create(
            code="person",
            defaults={
                "name": "Person",
                "serializer_path": "person.serializers.PersonSerializer"
            }
        )

        party, _ = Party.objects.get_or_create(
            id=uuid.uuid4(),
            object_id=person.id,
            content_type=ContentType.objects.get_for_model(Person),
            defaults={
                "name": "Test Customer Party",
                "party_type": party_type,
            }
        )

        kyc_status, _ = KYCStatus.objects.get_or_create(
            code="pending",
            defaults={"name": "Pending"}
        )

        # Now create the KYCRecord properly
        kyc, created = KYCRecord.objects.get_or_create(
            party=party,
            status=kyc_status,
            risk_score=50,         # required integer
            notes="Initial test KYC record"
        )

        signal = AutomationTestFactory.emit_signal(
            "kyc_record_created",
            obj=kyc
        )
        self.assertTrue(AutomationTestFactory.signal_created("kyc_record_created"))

        # Run automation
        AutomationTestFactory.run_signal(signal)
    
        self.__class__.logger.error((f"CELERY_TASK_ALWAYS_EAGER: {CELERY_TASK_ALWAYS_EAGER} \nCELERY_TASK_EAGER_PROPAGATES: {CELERY_TASK_EAGER_PROPAGATES}"))
        time.sleep(15)
        # Verify alert
        triggers = AutomationTrigger.objects.filter(signal_type=signal.signal_type)
        for t in triggers:
            self.__class__.logger.error(f"Trigger: {t}")
            AutomationTestFactory.run_trigger(t)
        self.assertEqual(AutomationTestFactory.count_alerts(), 1)
