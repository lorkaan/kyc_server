import pandas as pd
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from agenda.models import (
    AgendaEventType,
    AgendaEventTypeAlertSchedule,
)
from watchdog.models import AlertSeverity
from agenda.models import TimeMeasurement


class Command(BaseCommand):

    help = "Import Agenda Event Type Alert Schedules from CSV / Excel / ODS"

    def add_arguments(self, parser):

        parser.add_argument(
            "file",
            type=str,
            help="Path to CSV / Excel / ODS file",
        )

    # --------------------------------------------------
    # Handle
    # --------------------------------------------------

    @transaction.atomic
    def handle(self, *args, **options):

        file_path = Path(options["file"])

        if not file_path.exists():
            raise CommandError("File not found")

        df = self.load_file(file_path)
        df = self.normalize_dataframe(df)
        self.validate_columns(df)
        self.import_rows(df)

        self.stdout.write(
            self.style.SUCCESS(
                "Agenda Event Type Alert Schedules imported successfully"
            )
        )

    # --------------------------------------------------
    # Load
    # --------------------------------------------------

    def load_file(self, path: Path) -> pd.DataFrame:

        suffix = path.suffix.lower()

        try:
            if suffix == ".csv":
                return pd.read_csv(path)

            elif suffix in (".xls", ".xlsx"):
                return pd.read_excel(path)

            elif suffix == ".ods":
                return pd.read_excel(path, engine="odf")

            else:
                raise CommandError(f"Unsupported file format: {suffix}")

        except Exception as e:
            raise CommandError(f"Failed to read file: {e}")

    # --------------------------------------------------
    # Normalize
    # --------------------------------------------------

    def normalize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:

        df.columns = df.columns.str.strip().str.lower()
        df = df.fillna("")

        for col in df.columns:
            df[col] = df[col].astype(str).str.strip()

        return df

    # --------------------------------------------------
    # Validation
    # --------------------------------------------------

    def validate_columns(self, df: pd.DataFrame):

        required = {
            "event_type",
            "value",
            "measurement",
        }

        missing = required - set(df.columns)

        if missing:
            raise CommandError(
                f"Missing required columns: {', '.join(missing)}"
            )

    # --------------------------------------------------
    # Import
    # --------------------------------------------------

    def import_rows(self, df: pd.DataFrame):

        for index, row in df.iterrows():
            try:
                self.import_row(row)
            except Exception as e:
                raise CommandError(f"Row {index + 2}: {e}")

    # --------------------------------------------------
    # Row import
    # --------------------------------------------------

    def import_row(self, row: pd.Series):

        def resolve_event_type(value: str) -> AgendaEventType:
            return AgendaEventType.objects.get(code=value)

        def resolve_severity(value: str):
            if not value:
                return None
            return AlertSeverity.objects.get(code=value)

        def resolve_measurement(value: str) -> str:
            value = value.strip().upper()

            mapping = {
                "HOURLY": TimeMeasurement.HOURLY,
                "DAILY": TimeMeasurement.DAILY,
                "WEEKLY": TimeMeasurement.WEEKLY,
                "MONTHLY": TimeMeasurement.MONTHLY,
                "YEARLY": TimeMeasurement.YEARLY,
                # allow single-char too
                "H": TimeMeasurement.HOURLY,
                "D": TimeMeasurement.DAILY,
                "W": TimeMeasurement.WEEKLY,
                "M": TimeMeasurement.MONTHLY,
                "Y": TimeMeasurement.YEARLY,
            }

            if value not in mapping:
                raise ValueError(f"Invalid measurement: {value}")

            return mapping[value]

        event_type = resolve_event_type(row["event_type"])
        measurement = resolve_measurement(row["measurement"])
        value = int(row["value"])
        severity = resolve_severity(row.get("severity", ""))

        obj, created = AgendaEventTypeAlertSchedule.objects.update_or_create(
            event_type=event_type,
            value=value,
            measurement=measurement,
            defaults={
                "severity": severity,
            },
        )

        action = "Created" if created else "Updated"

        self.stdout.write(
            f"{action}: {event_type.code} -> {value} {measurement}"
        )