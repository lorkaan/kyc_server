# your_app/management/commands/import_field_labels.py

import pandas as pd

from django.core.management.base import BaseCommand, CommandError
from django.contrib.contenttypes.models import ContentType

from modellabels.models import ModelFieldLabel


class Command(BaseCommand):
    help = "Import ModelFieldLabel data from CSV, Excel, or ODS file"

    def add_arguments(self, parser):
        parser.add_argument(
            "file_path",
            type=str,
            help="Path to the input file (.csv, .xlsx, .ods)"
        )

    def handle(self, *args, **options):
        file_path = options["file_path"]

        try:
            if file_path.endswith(".csv"):
                df = pd.read_csv(file_path)
            elif file_path.endswith(".xlsx"):
                df = pd.read_excel(file_path)
            elif file_path.endswith(".ods"):
                df = pd.read_excel(file_path, engine="odf")
            else:
                raise CommandError("Unsupported file format. Use CSV, XLSX, or ODS.")
        except Exception as e:
            raise CommandError(f"Error reading file: {e}")

        required_columns = {"content_type", "field_name", "label"}
        missing = required_columns - set(df.columns)
        if missing:
            raise CommandError(f"Missing required columns: {missing}")

        created_count = 0
        updated_count = 0

        for _, row in df.iterrows():
            try:
                app_label, model = row["content_type"].split(".")
                content_type = ContentType.objects.get(
                    app_label=app_label,
                    model=model
                )
            except Exception:
                self.stderr.write(
                    f"Invalid content_type: {row.get('content_type')}"
                )
                continue

            obj, created = ModelFieldLabel.objects.update_or_create(
                content_type=content_type,
                field_name=row["field_name"],
                defaults={
                    "label": row["label"],
                    "description": row.get("description", ""),
                }
            )

            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Import complete: {created_count} created, {updated_count} updated"
            )
        )