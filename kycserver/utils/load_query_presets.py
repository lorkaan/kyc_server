import json
from pathlib import Path
from django.core.exceptions import ValidationError

from .model_utils import getModelFromName
from storedquery.models import SavedQuery

from users.models import User

def import_saved_queries(query_list, owner: User = None):
    """
    Parses a list of query definitions and stores them as SavedQuery instances.
    
    Parameters:
    - query_list: list of dicts, each dict representing a saved query.
    - owner: optional User object. Must be None for system queries.
    """
    created_queries = []

    for qdef in query_list:
        name = qdef.get("name")
        description = qdef.get("description", "")
        is_system = qdef.get("is_system", False)
        query_obj = qdef.get("query", {})

        # Validate name and query
        if not name or not query_obj:
            raise ValueError(f"Query definition missing required fields: {qdef}")

        # Extract model info
        model_label = query_obj.get("model")
        if not model_label:
            raise ValueError(f"Query {name} missing 'model' key in query")

        # Validate model exists
        try:
            model_cls = getModelFromName(model_label)
        except (ValueError, LookupError):
            raise ValueError(f"Query {name} references invalid model: {model_label}")

        # Extract params and AST query
        params_def = query_obj.get("params", {})
        ast_query = query_obj.get("query", {})
        field_defs = query_obj.get("fields", None)
        field_defaults = query_obj.get("default_fields", None)

        # Construct final JSON for storage
        json_for_storage = {
            "params": params_def,
            "query": ast_query,
        }

        if type(field_defs) == list  and len(field_defs) > 0:
            json_for_storage["fields"] = field_defs

        if type(field_defaults) == list  and len(field_defaults) > 0:
            json_for_storage["default_fields"] = field_defaults

        # Determine owner
        if is_system:
            final_owner = None
        else:
            final_owner = owner

        # Create or update the SavedQuery
        saved_query, created = SavedQuery.objects.update_or_create(
            name=name,
            model=model_label,
            defaults={
                "description": description,
                "query": json_for_storage,
                "owner": final_owner,
                "is_system": is_system
            }
        )

        created_queries.append(saved_query)

    return created_queries

def import_queries_from_file(json_path: str, owner: User = None):
    """
    Reads query definitions from a JSON file and imports them into SavedQuery.
    
    :param json_path: Path to JSON file containing a list of query definitions.
    :param owner: Optional User instance for non-system queries.
    :return: List of SavedQuery instances created/updated.
    """
    json_path = Path(json_path)
    if not json_path.exists() or not json_path.is_file():
        raise FileNotFoundError(f"JSON file not found: {json_path}")

    with open(json_path, "r", encoding="utf-8") as f:
        try:
            query_defs = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON file: {e}")

    if not isinstance(query_defs, list):
        raise ValueError("JSON file must contain a list of query definitions")

    created_queries = import_saved_queries(query_defs, owner=owner)
    return created_queries