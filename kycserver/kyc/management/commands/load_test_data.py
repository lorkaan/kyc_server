from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from django.contrib.contenttypes.models import ContentType

from kyc.data_types import AnswerTypeEnum
from person.models import Person
from company.models import Company
from kyc.models import (
    KYCStatus,
    KYCRecord,
    KycQuestion,
    KycAnswer,
)
from watchdog.models import Alert, AlertStatus, AlertSeverity, AlertReason


class Command(BaseCommand):
    help = "Load deterministic test data for query testing"

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("Loading test data…")

        # --------------------
        # Reference tables
        # --------------------
        active_status, _ = KYCStatus.objects.get_or_create(
            code="ACTIVE",
            defaults={"name": "Active", "is_terminal": False},
        )

        closed_kyc_status, _ = KYCStatus.objects.get_or_create(
            code="CLOSED",
            defaults={"name": "Closed", "is_terminal": True},
        )

        # --------------------
        # People
        # --------------------
        alice, _ = Person.objects.get_or_create(
            first_name="Alice",
            last_name="Smith",
            date_of_birth="1990-01-01",
            nationality="US",
        )

        bob, _ = Person.objects.get_or_create(
            first_name="Bob",
            last_name="Jones",
            date_of_birth="1985-06-15",
            nationality="GB",
        )

        # --------------------
        # Company
        # --------------------
        acme, _ = Company.objects.get_or_create(
            name="Acme Corp",
            registration_number="ACME-001",
            country="US",
        )

        # --------------------
        # KYC Records
        # --------------------
        alice_kyc = KYCRecord.objects.create(
            person=alice,
            status=active_status,
            risk_score=42,
            notes="Low risk",
            is_current=True,
        )

        bob_kyc_old = KYCRecord.objects.create(
            person=bob,
            status=closed_kyc_status,
            risk_score=88,
            notes="Old KYC",
            is_current=False,
        )

        bob_kyc_current = KYCRecord.objects.create(
            person=bob,
            status=active_status,
            risk_score=65,
            notes="Current KYC",
            is_current=True,
        )

        # --------------------
        # Questions
        # --------------------
        income_q, _ = KycQuestion.objects.get_or_create(
            key="annual_income",
            defaults={
                "label": "Annual Income",
                "answer_type": AnswerTypeEnum.NUMBER,
                "required": True,
                "order": 1,
            },
        )

        pep_q, _ = KycQuestion.objects.get_or_create(
            key="is_pep",
            defaults={
                "label": "Politically Exposed Person",
                "answer_type": AnswerTypeEnum.BOOL,
                "required": True,
                "order": 2,
            },
        )

        # --------------------
        # Answers
        # --------------------
        KycAnswer.objects.create(
            kyc_record=alice_kyc,
            question=income_q,
            value_number=75000,
        )

        KycAnswer.objects.create(
            kyc_record=alice_kyc,
            question=pep_q,
            value_bool=False,
        )

        KycAnswer.objects.create(
            kyc_record=bob_kyc_current,
            question=income_q,
            value_number=120000,
        )

        # --------------------
        # Alert reference data (MUST exist)
        # --------------------
        high = AlertSeverity.objects.get(code="high")
        medium = AlertSeverity.objects.get(code="medium")

        open_alert_status, _ = AlertStatus.objects.get_or_create(
            code="open",
            defaults={"name": "Open", "is_terminal": False},
        )

        closed_alert_status, _ = AlertStatus.objects.get_or_create(
            code="resolved",
            defaults={"name": "Resolved", "is_terminal": True},
        )

        reason = AlertReason.objects.get(code="KYC_EXPIRED")

        # --------------------
        # Alerts (GenericForeignKey-safe)
        # --------------------
        person_ct = ContentType.objects.get_for_model(Person)

        Alert.objects.create(
            reason=reason,
            severity=high,
            status=open_alert_status,
            content_type=person_ct,
            object_id=alice.id,
            message="KYC requires review",
            triggered_at=timezone.now(),
        )

        Alert.objects.create(
            reason=reason,
            severity=medium,
            status=closed_alert_status,
            content_type=person_ct,
            object_id=bob.id,
            message="Resolved alert",
            triggered_at=timezone.now(),
        )

        self.stdout.write(self.style.SUCCESS("Test data loaded successfully"))
