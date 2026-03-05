import pandas as pd
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from kyc.models import (
    ReferenceSet,
    ReferenceValue,
)


class Command(BaseCommand):

    help = "Import Reference Sets and Values from CSV / Excel using Pandas"

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
            self.style.SUCCESS(
                "Reference sets imported successfully"
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
            "set_key",
            "set_name",
            "value_code",
            "value_label",
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

                raise CommandError(
                    f"Row {index + 2}: {e}"
                )

    def import_row(self, row: pd.Series):

        def to_int(v, default=0):
            try:
                return int(float(v))
            except Exception:
                return default

        # -----------------------------
        # Reference Set
        # -----------------------------

        reference_set, created = ReferenceSet.objects.get_or_create(
            key=row["set_key"],
            defaults={
                "name": row["set_name"],
                "description": "",
                "is_active": True,
            },
        )

        # Only update fields if they are provided
        updated = False

        if reference_set.name != row["set_name"]:
            reference_set.name = row["set_name"]
            updated = True

        description = row.get("set_description", "")

        if description and reference_set.description != description:
            reference_set.description = description
            updated = True

        if updated:
            reference_set.save()

        # -----------------------------
        # Reference Value
        # -----------------------------

        ReferenceValue.objects.update_or_create(
            reference_set=reference_set,
            code=row["value_code"],
            defaults={
                "label": row["value_label"],
                "order": to_int(row.get("value_order")),
                "is_active": True,
            },
        )