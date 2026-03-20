import json
import os
import pandas as pd

from django.core.management.base import BaseCommand
from django.db import transaction

from kyc.models import KycCondition, KycQuestion


class Command(BaseCommand):
    help = "Import KYC Conditions with external JSON rules"

    def add_arguments(self, parser):
        parser.add_argument("file_path", type=str)
        parser.add_argument(
            "--rules-dir",
            type=str,
            default=None,
            help="Directory containing JSON rule files"
        )

    def load_file(self, file_path):
        if file_path.endswith(".csv"):
            return pd.read_csv(file_path)

        elif file_path.endswith(".xlsx"):
            return pd.read_excel(file_path)

        elif file_path.endswith(".ods"):
            return pd.read_excel(file_path, engine="odf")

        else:
            raise ValueError("Unsupported file format")

    def load_rule(self, rules_dir, filename):
        if not filename:
            raise ValueError("Missing rule_file")

        path = filename
        if rules_dir:
            path = os.path.join(rules_dir, filename)

        if not os.path.exists(path):
            raise FileNotFoundError(f"Rule file not found: {path}")

        with open(path, "r") as f:
            return json.load(f)

    @transaction.atomic
    def handle(self, *args, **options):
        file_path = options["file_path"]
        rules_dir = options["rules_dir"]

        df = self.load_file(file_path)

        created = 0

        for index, row in df.iterrows():
            try:
                question = KycQuestion.objects.get(
                    key=row["target_question"]
                )

                # ✅ Load JSON from file
                rule = self.load_rule(
                    rules_dir,
                    row["rule_file"]
                )

                condition, _ = KycCondition.objects.update_or_create(
                    target_question=question,
                    condition_type=row["condition_type"],
                    priority=int(row.get("priority", 0)),
                    defaults={
                        "rule": rule,
                        "description": row.get("description", ""),
                        "is_active": bool(row.get("is_active", True)),
                    }
                )

                created += 1

            except Exception as e:
                self.stderr.write(
                    f"Row {index} failed: {e}"
                )
                raise

        self.stdout.write(
            self.style.SUCCESS(f"Imported {created} conditions")
        )