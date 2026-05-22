import pandas as pd
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from automation.models import AutomationRule
from storedquery.models import SavedQuery


class Command(BaseCommand):

    help = "Import Automation Rules from CSV / Excel / ODS"

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
                "Automation Rules imported successfully"
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
            raise CommandError(
                f"Failed to read file: {e}"
            )

    # --------------------------------------------------
    # Normalize
    # --------------------------------------------------

    def normalize_dataframe(
        self,
        df: pd.DataFrame
    ) -> pd.DataFrame:

        df.columns = (
            df.columns
            .str.strip()
            .str.lower()
        )

        df = df.fillna("")

        for col in df.columns:

            df[col] = (
                df[col]
                .astype(str)
                .str.strip()
            )

        return df

    # --------------------------------------------------
    # Validation
    # --------------------------------------------------

    def validate_columns(
        self,
        df: pd.DataFrame
    ):

        required = {
            "name",
            "query",
        }

        missing = required - set(df.columns)

        if missing:

            raise CommandError(
                f"Missing required columns: "
                f"{', '.join(missing)}"
            )

    # --------------------------------------------------
    # Import
    # --------------------------------------------------

    def import_rows(
        self,
        df: pd.DataFrame
    ):

        for index, row in df.iterrows():

            try:

                self.import_row(row)

            except Exception as e:

                raise CommandError(
                    f"Row {index + 2}: {e}"
                )

    def import_row(
        self,
        row: pd.Series
    ):

        query_name = row["query"]

        query = SavedQuery.objects.filter(name=query_name).first()
        if query == None:
            raise ValueError(
                f"SavedQuery not found: {query_name}"
            )

        rule, created = (
            AutomationRule.objects.update_or_create(
                name=row["name"],
                defaults={
                    "query": query,
                }
            )
        )

        action = (
            "Created"
            if created
            else "Updated"
        )

        self.stdout.write(
            f"{action}: "
            f"{rule.name}"
        )