import pandas as pd
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from kyc.models import (
    KycQuestion,
    KycQuestionGroup,
    ReferenceSet,
)


class Command(BaseCommand):

    help = "Import KYC Questions from CSV / Excel using Pandas"


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
            self.style.SUCCESS("KYC import completed successfully")
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
        """
        Cleanup common client mistakes
        """

        # Normalize headers
        df.columns = (
            df.columns
            .str.strip()
            .str.lower()
        )

        # Replace NaN with empty string
        df = df.fillna("")

        # Strip whitespace everywhere
        for col in df.columns:
            df[col] = df[col].astype(str).str.strip()

        return df


    # --------------------------------------------------
    # Validation
    # --------------------------------------------------

    def validate_columns(self, df: pd.DataFrame):

        required = {
            "group_key",
            "group_label",
            "group_order",
            "group_required",
            "group_repeatable",

            "question_key",
            "question_label",
            "answer_type",
            "required",
            "order",

            "repeatable",
            "requires_document",
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
        # Group
        # -----------------------------

        group, _ = KycQuestionGroup.objects.update_or_create(
            key=row["group_key"],
            defaults={
                "label": row["group_label"],
                "order": to_int(row["group_order"]),
                "required": to_bool(row["group_required"]),
                "is_repeatable": to_bool(row["group_repeatable"]),
            },
        )


        # -----------------------------
        # Reference Set (optional)
        # -----------------------------

        reference_set = None

        ref_key = row.get("reference_set_key", "")

        if ref_key:

            reference_set, _ = ReferenceSet.objects.update_or_create(
                key=ref_key,
                defaults={
                    "name": row.get("reference_set_name", "")
                }
            )


        # -----------------------------
        # Question
        # -----------------------------

        KycQuestion.objects.update_or_create(
            key=row["question_key"],
            defaults={

                "label": row["question_label"],

                "group": group,

                "answer_type": row["answer_type"],

                "required": to_bool(row["required"]),

                "order": to_int(row["order"]),

                "is_repeatable": to_bool(row["repeatable"]),

                "requires_document": to_bool(
                    row["requires_document"]
                ),

                "reference_set": reference_set,
            },
        )