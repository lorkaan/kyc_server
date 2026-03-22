from django.db.models import Q, Exists, OuterRef

from globalparams.models import GlobalParameter
from utils.dsl_evaluator import DslEvaluator

from .model_utils import getModelFromName

from .dict_utils import dictToStr, isDict
from .type_utils import isFloat, isInteger, isList, isNumber, isString

from company.models import Company
from kyc.models import KYCRecord, KYCStatus, KycAnswer, KycAnswerOption, KycQuestion, RelationshipRole
from person.models import Person
from watchdog.models import Alert, AlertReason, AlertSeverity, AlertStatus, Signal, SignalSeverity, SignalType

from users.models import User

import pghistory
from django.apps import apps
from django.db import models
from copy import deepcopy
from datetime import datetime
import uuid

class QueryAstHandler(DslEvaluator):

    eval_statement_key = "query.where"

    MAX_DEPTH = 4 # To stop queries going too deep

    OPS = {
        "eq": "",
        "neq": "",
        "lt": "__lt",
        "lte": "__lte",
        "gt": "__gt",
        "gte": "__gte",
        "contains": "__icontains",
        "in": "__in",
        "isnull": "__isnull"
    }

    ENTITY_REGISTRY = { # Unused as of this moment
        User,
        Company,
        Person,
        RelationshipRole,
        KYCStatus,
        KYCRecord,
        KycQuestion,
        KycAnswer,
        KycAnswerOption,
        AlertStatus,
        AlertSeverity,
        AlertReason,
        Alert,
        SignalSeverity,
        SignalType,
        Signal
    }

    @classmethod
    def validate_params(cls, param_def: dict, params: dict):
        """
        Validate parameter values against the definitions and inject defaults.
        Supports:
        - Required vs optional
        - Default values (mutates `params`)
        - Type checking (including ISO datetime strings)
        """
        if not isinstance(param_def, dict):
            return True
        if not isinstance(params, dict):
            params = {}

        # Check for missing required params
        for name, spec in param_def.items():
            if spec.get("required", False) and name not in params:
                raise ValueError(f"Missing required param: {name}")

        # Inject defaults for optional params
        for name, spec in param_def.items():
            if name not in params and "default" in spec:
                params[name] = spec["default"]

        # Check for unknown params
        for name in params:
            if name not in param_def:
                raise ValueError(f"Unknown param: {name}")

        # Type validation
        for name, value in params.items():
            expected_type = param_def[name].get("type")
            if expected_type == "datetime":
                if hasattr(value, "isoformat"):
                    continue
                elif isinstance(value, str):
                    try:
                        datetime.fromisoformat(value.replace("Z", "+00:00"))
                    except ValueError:
                        raise ValueError(f"Param {name} must be ISO datetime string or datetime object")
                else:
                    raise ValueError(f"Param {name} must be datetime or ISO string")
            elif expected_type == "string":
                if isString(value, 0):
                    continue
                else:
                    raise ValueError(f"Param {name} must be a string")
            elif expected_type == "int":
                if isInteger(value):
                    continue
                else:
                    raise ValueError(f"Param {name} must be an Integer")
            elif expected_type == "float":
                if isFloat(value):
                    continue
                else:
                    raise ValueError(f"Param {name} must be a Float")
            elif expected_type == "number":
                if isNumber(value):
                    continue
                else:
                    raise ValueError(f"Param {name} must be a Number")
            elif expected_type == "boolean":
                if type(value) == bool:
                    continue
                else:
                    raise ValueError(f"Param {name} must be a Boolean")
            elif expected_type == "uuid":
                try:
                    # Accept both UUID objects and valid UUID strings
                    if isinstance(value, uuid.UUID):
                        continue
                    elif isinstance(value, str):
                        uuid.UUID(value)  # will raise ValueError if invalid
                    else:
                        raise ValueError
                except ValueError:
                    raise ValueError(f"Param {name} must be a valid UUID")
        return True

    @classmethod
    def _get_history_model(model):
        """
        Return the pghistory Event model for a tracked model.
        """
        for m in apps.get_models():
            if issubclass(m, pghistory.models.Event):
                if getattr(m, "pgh_model", None) is model:
                    return m
        return None

    @classmethod
    def _resolve_lookup_path(root_model, lookup):
        """ This is from the ModelInterface set up in the automation ingestion engine
        Validates and resolves a Django-style lookup path.
        Returns (final_model, django_lookup)
        """
        parts = lookup.split("__")
        current_model = root_model

        for i, part in enumerate(parts):
            try:
                field = current_model._meta.get_field(part)
            except Exception:
                # Remaining parts are lookup operators (icontains, in, etc)
                return current_model, "__".join(parts[i:])

            if field.is_relation:
                current_model = field.related_model
            else:
                # terminal concrete field
                return current_model, "__".join(parts[i:])

        return current_model, ""
    
    @classmethod
    def _compile_and(cls, root_model, children):
        if not isList(children):
            raise ValueError(f"Expected a list for AND operations, instead got: {type(children)} ==> {children}")
        
        q = Q()
        for child in children:
            if child is None:
                continue  # skip optional filter not provided
            child_q = cls.compile(root_model, child)
            if child_q:
                q &= child_q
        return q

    @classmethod
    def _compile_or(cls, root_model, children):
        if not isList(children):
            raise ValueError(f"Expected a list for OR operations, instead got: {type(children)} ==> {children}")
        
        q = Q()
        has_valid = False
        for child in children:
            if child is None:
                continue
            child_q = cls.compile(root_model, child)
            if child_q:
                q |= child_q
                has_valid = True
        if not has_valid:
            return None  # entire OR block is empty → return None
        return q

    @classmethod
    def _compile_predicate(cls, root_model, spec):
        if spec is None:
            return None  # skip missing optional predicate

        if not isDict(spec, ["field", "op", "value"]):
            raise ValueError(f"Expected a dictionary with the keys field, op, value. instead got: {type(spec)} ==> {spec}")

        field = spec["field"]
        op = spec["op"]
        value = spec.get("value")

        # If value is None (optional param not provided), skip this predicate
        if value is None:
            return None

        if op not in cls.OPS:
            raise ValueError(f"Unsupported operator: {op}")

        final_model, lookup = cls._resolve_lookup_path(root_model, field)

        if field.count("__") > cls.MAX_DEPTH:
            raise ValueError("Lookup path too deep")

        django_lookup = field + cls.OPS[op]
        q = Q(**{django_lookup: value})

        if op == "neq":
            q = ~q

        return q

    @classmethod
    def _compile_exists(cls, root_model, spec):
        if not isDict(spec, ["field", "op", "value"]):
            raise ValueError(f"Expected a dictionary with the keys field, op, value. instead got: {type(spec)} ==> {spec}")
        field = spec["field"]
        op = spec["op"]
        value = spec.get("value")

        final_model, lookup = cls._resolve_lookup_path(
            root_model, field
        )

        django_lookup = lookup + cls.OPS[op]

        # correlated subquery
        sub_qs = final_model.objects.filter(
            **{django_lookup: value}
        ).filter(
            **{final_model._meta.pk.name: OuterRef("pk")}
        )

        return Exists(sub_qs)

    @classmethod
    def compile(cls, root_model, node):
        if node is None:
            return None  # skip entirely

        if "and" in node:
            return cls._compile_and(root_model, node["and"])
        if "or" in node:
            return cls._compile_or(root_model, node["or"])
        if "not" in node:
            inner_q = cls.compile(root_model, node["not"])
            return ~inner_q if inner_q else None
        if "exists" in node:
            return cls._compile_exists(root_model, node["exists"])
        if "history" in node:
            return cls._compile_history(root_model, node["history"])
        return cls._compile_predicate(root_model, node)
    
    @classmethod
    def _compile_history(cls, root_model, spec):
        history_model = cls._get_history_model(root_model)
        if history_model == None:
            raise ValueError(f"No History available for {root_model}")
        where_ast = spec.get("where", None)
        if where_ast == None:
            raise ValueError("History clause requires 'where' operator")
        history_q = cls.compile(history_model, where_ast)
        subquery = (
            history_model.objects
            .filter(history_q)
            .filter(pgh_obj_id=OuterRef('pk'))
        )
        return Exists(subquery)
    
    @classmethod
    def evaluate(cls, ast_obj, **kwargs):
        entity_name = kwargs.get("entity_name", None)
        if not isString(entity_name):
            raise ValueError(
                f"Expected model to be a non-empty string, instead got: "
                f"{type(entity_name)} ==> {entity_name}"
            )
        else:
            try:
                base_model = getModelFromName()
            except Exception:
                raise ValueError(f"Could not find a model for the given name: {entity_name}")
            if not issubclass(base_model, models.Model) or base_model not in cls.ENTITY_REGISTRY:
                raise ValueError(f"Model: {base_model} is not authorized to be queried")
            else:
                # ---- Compile + execute ----
                predicate = cls.compile(base_model, ast_obj)

                if predicate is None:
                    # Explicit decision: no predicate means empty filter (allowed)
                    return base_model.objects.all()

                return base_model.objects.filter(predicate)
    
    @classmethod
    def run(cls, query_def, params={}, **kwargs):
        # ---- Top-level validation ----
        if not isDict(query_def, keys=["query", "model"]):
            raise ValueError(
                f"Expected a Dictionary with keys query, model, but got: "
                f"{type(query_def)} ==> {dictToStr(query_def) if isinstance(query_def, dict) else query_def}"
            )
        else:
            return super().run(query_def, params, **kwargs)