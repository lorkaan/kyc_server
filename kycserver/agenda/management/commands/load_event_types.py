import pandas as pd
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from agenda.models import AgendaEventType


class Command(BaseCommand):

    help = "Import Agenda Event Types from CSV / Excel / ODS using Pandas"

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
                "Agenda Event Types imported successfully"
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
            "name",
            "code",
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

        def to_bool(value, default=True):

            if value is None:
                return default

            value = str(value).strip().lower()

            if value in ("true", "1", "yes", "y"):
                return True

            if value in ("false", "0", "no", "n"):
                return False

            return default

        code = row["code"]

        defaults = {
            "name": row["name"],
            "description": row.get("description", ""),
            "is_active": to_bool(
                row.get("is_active", True)
            ),
        }

        event_type, created = AgendaEventType.objects.update_or_create(
            code=code,
            defaults=defaults,
        )

        action = "Created" if created else "Updated"

        self.stdout.write(
            f"{action}: {event_type.name} ({event_type.code})"
        )