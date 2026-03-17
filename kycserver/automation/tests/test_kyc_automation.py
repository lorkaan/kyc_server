from django.test import TestCase
import uuid

from kyc.models import KYCRecord, KYCStatus
from automation.tests.utils.automation_factory import AutomationTestFactory
from person.models import Person
from party.models import Party, PartyType

from django.contrib.contenttypes.models import ContentType
from datetime import date


class KycAutomationTests(TestCase):

    def test_kyc_creation_creates_alert(self):

        # Create trigger + action
        AutomationTestFactory.signal_trigger(
            signal_type="kyc_record_created",
            action_type="create_alert",
            config={"title": "KYC Created"}
        )

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
            name="Pending"
        )

        # Now create the KYCRecord properly
        kyc, created = KYCRecord.objects.get_or_create(
            id=uuid.uuid4(),
            party=party,
            status=kyc_status,
            risk_score=50,         # required integer
            notes="Initial test KYC record",
            is_current=True
        )

        if created:
            # Emit signal
            signal = AutomationTestFactory.emit_signal(
                "kyc_record_created",
                obj=kyc
            )

            # Run automation
            AutomationTestFactory.run_signal(signal)

            # Verify alert
            self.assertTrue(
                AutomationTestFactory.alert_created()
            )
        else:
            self.assertTrue(False)
