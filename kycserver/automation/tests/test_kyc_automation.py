from django.test import TestCase
import uuid

from kyc.models import KYCRecord
from automation.tests.utils.automation_factory import AutomationTestFactory


class KycAutomationTests(TestCase):

    def test_kyc_creation_creates_alert(self):

        # Create trigger + action
        AutomationTestFactory.signal_trigger(
            signal_type="kyc_record_created",
            action_type="create_alert",
            config={"title": "KYC Created"}
        )

        # Create KYC record
        kyc = KYCRecord.objects.create(
            id=uuid.uuid4(),
            name="Test Customer"
        )

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
