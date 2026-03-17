import pandas as pd
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from automation.models import AutomationRule, AutomationTrigger, AutomationAction
from watchdog.models import SignalType
import logging


class Command(BaseCommand):

    logger = logging.getLogger()

    help = "Import Automation Signals, Triggers, and Actions from CSV / Excel / ODS"

    def add_arguments(self, parser):
        parser.add_argument(
            "file",
            type=str,
            help="Path to CSV / Excel / ODS file",
        )

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
            self.style.SUCCESS("Automation import completed successfully")
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
        required = {"trigger_name", "trigger_type"}
        self.__class__.logger.error(f"COLUMNS FOUND: {df.columns}")
        missing = required - set(df.columns)
        if missing:
            raise CommandError(f"Missing required columns: {', '.join(missing)}")

    # --------------------------------------------------
    # Import
    # --------------------------------------------------
    def import_rows(self, df: pd.DataFrame):
        for index, row in df.iterrows():
            try:
                self.import_row(row)
            except Exception as e:
                raise CommandError(f"Row {index + 2}: {e}")

    def import_row(self, row: pd.Series):

        # -----------------------------
        # Helpers
        # -----------------------------
        def to_bool(v):
            return str(v).lower() in ("1", "true", "yes", "y", "t")

        # -----------------------------
        # SignalType (optional)
        # -----------------------------
        signal_type = None
        signal_name = row.get("signal_type", "")

        if signal_name:
            signal_type, _ = SignalType.objects.get_or_create(
                label=signal_name
            )

        # -----------------------------
        # Rule (optional)
        # -----------------------------
        rule = None
        rule_name = row.get("rule_name", "")

        if rule_name:
            rule, _ = AutomationRule.objects.get_or_create(
                name=rule_name
            )

        # -----------------------------
        # Trigger Type
        # -----------------------------
        trigger_type = row.get("trigger_type", "").upper()

        if trigger_type not in ("S", "T"):
            raise ValueError("trigger_type must be 'S' (signal) or 'T' (time)")

        # -----------------------------
        # Schedule
        # -----------------------------
        schedule = row.get("schedule", "").upper() or None

        # -----------------------------
        # Validation (CRITICAL)
        # -----------------------------
        if trigger_type == "S" and not signal_type:
            raise ValueError("Signal trigger requires signal_type")

        if trigger_type == "T" and not schedule:
            raise ValueError("Time trigger requires schedule")

        # -----------------------------
        # Trigger
        # -----------------------------
        trigger, _ = AutomationTrigger.objects.update_or_create(
            name=row["trigger_name"],  # assuming BaseModel has name
            defaults={
                "trigger_type": trigger_type,
                "signal_type": signal_type if trigger_type == "S" else None,
                "schedule": schedule if trigger_type == "T" else None,
                "rule": rule,
                "is_active": to_bool(row.get("is_active", "true")),
            }
        )

