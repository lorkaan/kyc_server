import json
import uuid
from datetime import datetime

import pandas as pd
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.dateparse import parse_datetime

from globalparams.models import (
    GlobalParameter,
    StringValue,
    IntValue,
    FloatValue,
    BooleanValue,
    UUIDValue,
    DateTimeValue,
    JsonValue,
)


"""
Type mappings:

    S → String
    I → Integer
    F → Float
    B → Boolean
    U → UUID
    D → Datetime
    J → JSON
"""


class Command(BaseCommand):
    help = "Import GlobalParameters and their values from CSV/XLSX/ODS"

    VALUE_MODEL_MAP = {
        GlobalParameter.Type.STRING: StringValue,
        GlobalParameter.Type.INT: IntValue,
        GlobalParameter.Type.FLOAT: FloatValue,
        GlobalParameter.Type.BOOLEAN: BooleanValue,
        GlobalParameter.Type.UUID: UUIDValue,
        GlobalParameter.Type.DATETIME: DateTimeValue,
        GlobalParameter.Type.JSON: JsonValue,
    }

    def add_arguments(self, parser):
        parser.add_argument(
            "file_path",
            type=str,
            help="Path to CSV/XLSX/ODS file"
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

    def parse_bool(self, value):
        if isinstance(value, bool):
            return value

        if pd.isna(value):
            return False

        return str(value).strip().lower() in (
            "1", "true", "yes", "y", "t"
        )

    def parse_value(self, param_type, raw_value):
        """
        Convert spreadsheet values into typed Python values.
        """

        if pd.isna(raw_value):
            return None

        if param_type == GlobalParameter.Type.STRING:
            return str(raw_value)

        elif param_type == GlobalParameter.Type.INT:
            return int(raw_value)

        elif param_type == GlobalParameter.Type.FLOAT:
            return float(raw_value)

        elif param_type == GlobalParameter.Type.BOOLEAN:
            return self.parse_bool(raw_value)

        elif param_type == GlobalParameter.Type.UUID:
            return uuid.UUID(str(raw_value))

        elif param_type == GlobalParameter.Type.DATETIME:
            if isinstance(raw_value, datetime):
                return raw_value

            parsed = parse_datetime(str(raw_value))
            if not parsed:
                raise ValueError(f"Invalid datetime value: {raw_value}")

            return parsed

        elif param_type == GlobalParameter.Type.JSON:
            if isinstance(raw_value, dict):
                return raw_value

            return json.loads(raw_value)

        raise ValueError(f"Unsupported parameter type: {param_type}")

    @transaction.atomic
    def handle(self, *args, **options):
        file_path = options["file_path"]
        df = self.load_file(file_path)

        imported = 0

        for index, row in df.iterrows():
            try:
                param_type = row["type"]

                if param_type not in self.VALUE_MODEL_MAP:
                    raise ValueError(f"Unsupported type '{param_type}'")

                value_model = self.VALUE_MODEL_MAP[param_type]

                parsed_value = self.parse_value(
                    param_type,
                    row["value"]
                )

                parameter, _ = GlobalParameter.objects.update_or_create(
                    name=row["name"],
                    defaults={
                        "description": row.get("description", ""),
                        "type": param_type,
                        "is_active": self.parse_bool(
                            row.get("is_active", True)
                        ),
                    }
                )

                # --- HANDLE VALUE OBJECT CLEANLY ---

                existing_obj = parameter.content_object

                # If type changed → delete old object and clear relation
                if existing_obj and not isinstance(existing_obj, value_model):
                    existing_obj.delete()
                    parameter.set_target(None)
                    existing_obj = None

                # If correct type already exists → update it
                if existing_obj and isinstance(existing_obj, value_model):
                    existing_obj.value = parsed_value
                    existing_obj.save()
                    value_obj = existing_obj

                else:
                    # Create new value object
                    value_obj = value_model.objects.create(
                        value=parsed_value
                    )

                # Link via Generic FK (single source of truth)
                parameter.set_target(value_obj)

                imported += 1

            except Exception as e:
                self.stderr.write(f"Row {index} failed: {e}")
                raise

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {imported} global parameters"
            )
        )