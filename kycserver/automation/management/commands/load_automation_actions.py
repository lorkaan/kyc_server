import pandas as pd
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from automation.models import AutomationAction, AutomationTrigger
from utils.action_runner import ActionRunner
import logging

class Command(BaseCommand):

    logger = logging.getLogger()

    help = "Import Automation Actions from CSV / Excel using Pandas with external JSON configs"

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

        self.base_path = file_path.parent

        df = self.load_file(file_path)

        df = self.normalize_dataframe(df)

        self.validate_columns(df)

        self.import_rows(df)

        self.stdout.write(
            self.style.SUCCESS("Automation Actions import completed successfully")
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
                raise CommandError(
                    f"Unsupported file format: {suffix}"
                )

        except Exception as e:
            raise CommandError(f"Failed to read file: {e}")

    # --------------------------------------------------
    # Normalize
    # --------------------------------------------------

    def normalize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:

        df.columns = (
            df.columns
            .str.strip()
            .str.lower()
        )

        df = df.fillna("")

        for col in df.columns:
            df[col] = df[col].astype(str).str.strip()

        return df

    # --------------------------------------------------
    # Validation
    # --------------------------------------------------

    def validate_columns(self, df: pd.DataFrame):

        required = {
            "trigger_name",
            "action_type",
        }

        missing = required - set(df.columns)

        if missing:
            raise CommandError(
                f"Missing required columns: {', '.join(missing)}"
            )

    # --------------------------------------------------
    # JSON Loader
    # --------------------------------------------------

    def load_json_file(self, folder: str, filename: str):

        if not filename:
            return None

        file_path = self.base_path / folder / filename

        if not file_path.exists():
            raise ValueError(f"{folder} file '{filename}' not found")

        import json

        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except Exception as e:
            raise ValueError(f"Invalid JSON in {filename}: {e}")

    # --------------------------------------------------
    # Import
    # --------------------------------------------------

    def import_rows(self, df: pd.DataFrame):

        for index, row in df.iterrows():

            try:
                self.import_row(row)

            except Exception as e:

                raise CommandError(
                    f"Row {index + 2}: {e}"
                )

    def import_row(self, row: pd.Series):

        # -----------------------------
        # Helpers
        # -----------------------------

        def to_bool(v):
            return str(v).lower() in (
                "1", "true", "yes", "y", "t"
            )

        def to_int(v, default=0):
            try:
                return int(float(v))
            except Exception:
                return default

        # -----------------------------
        # Trigger (required if active)
        # -----------------------------

        trigger = None
        trigger_name = row.get("trigger_name", "")

        if trigger_name:

            try:
                trigger = AutomationTrigger.objects.get(
                    name=trigger_name
                )

            except AutomationTrigger.DoesNotExist:
                raise ValueError(
                    f"Trigger '{trigger_name}' does not exist"
                )

        # -----------------------------
        # Action Type
        # -----------------------------

        action_type = row.get("action_type", "")

        if not action_type:
            raise ValueError("action_type is required")

        if action_type not in ActionRunner.REGISTRY:
            self.__class__.logger.error(f"Action Type: {action_type} \n\t{ActionRunner.REGISTRY}")
            raise ValueError(
                f"Unknown action_type '{action_type}'"
            )

        # -----------------------------
        # Load Config / Condition
        # -----------------------------

        config = self.load_json_file(
            "action_configs",
            row.get("config_file", "")
        ) or {}

        condition = self.load_json_file(
            "action_conditions",
            row.get("condition_file", "")
        )

        # -----------------------------
        # Flags
        # -----------------------------

        is_active = to_bool(row.get("is_active", "true"))
        order = to_int(row.get("order", 0))

        # -----------------------------
        # Validation
        # -----------------------------

        if is_active and not trigger:
            raise ValueError(
                "Active action must have a trigger"
            )

        # -----------------------------
        # Create / Update
        # -----------------------------

        action, _ = AutomationAction.objects.update_or_create(
            trigger=trigger,
            type=action_type,
            order=order,
            defaults={
                "config": config,
                "condition": condition,
                "is_active": is_active,
            }
        )

        action.full_clean()
        action.save()
