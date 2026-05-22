from django.db.models import F, Q, Exists, Model, OuterRef

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
from datetime import date, datetime, timedelta
import uuid

class QueryAstHandler(DslEvaluator):

    precompute_functions = {
        "now": lambda : datetime.now().isoformat(),
        "now_date": lambda: datetime.now().date().isoformat(),
        "tomorrow_date": lambda: (datetime.now().date() + timedelta(days=1)).isoformat()
    }

    eval_statement_key = "query.where"

    model_name_key = "model"

    query_def_key = "query"

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
    def get_computed_params(cls, param_def: dict):
        precomputed_params = {}
        if isDict(param_def):
            for name, objDef in param_def.items():
                if objDef.get("type", "") != "computed":
                    continue
                else:
                    compute_func = cls.precompute_functions.get(name, None)
                    if callable(compute_func):
                        precomputed_params[name] = compute_func()
                    else:
                        continue
        return precomputed_params
            

    @classmethod
    def clean_params(cls, param_def: dict, params: dict):
        """
            This function will clean the parameters so it can be properly evaluated. 
            E.g. Set any non-required parameters to None if they do not have a value.
        """
        if not isinstance(params, dict):
            return {}
        if not isinstance(param_def, dict):
            raise ValueError(f"Expected a parameter dictionary to handle having parameters:\nParams: \n{dictToStr(params, prefix="\t")}\nInstead got: {type(param_def)} -> {param_def}")
        new_params = cls.get_computed_params(param_def)
        for name, value in params.items():
            if not param_def[name].get("required", False):
                expected_type = param_def[name].get("type")
                if expected_type == "datetime" and isinstance(value, str) and len(value) <= 0:
                    continue
                elif expected_type == "string" and isinstance(value, str) and len(value) <= 0:
                    continue
                elif expected_type == "uuid" and isinstance(value, str) and len(value) <= 0:
                    continue
                else:
                    new_params[name] = value
            else:
                new_params[name] = value
        cls.logger.error(f"Cleaned Params: \n{dictToStr(new_params, prefix="\t")}")
        return new_params

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
            required_flag = param_def[name].get("required", False)
            if required_flag or value != None:
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
                        raise ValueError(f"Param {name} must be a string, instead got {type(value)} --> {value}")
                elif expected_type == "int":
                    if isInteger(value):
                        continue
                    else:
                        raise ValueError(f"Param {name} must be an Integer, instead got {type(value)} --> {value}")
                elif expected_type == "float":
                    if isFloat(value):
                        continue
                    else:
                        raise ValueError(f"Param {name} must be a Float, instead got {type(value)} --> {value}")
                elif expected_type == "number":
                    if isNumber(value):
                        continue
                    else:
                        raise ValueError(f"Param {name} must be a Number, instead got {type(value)} --> {value}")
                elif expected_type == "boolean":
                    if type(value) == bool:
                        continue
                    else:
                        raise ValueError(f"Param {name} must be a Boolean, instead got {type(value)} --> {value}")
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
                        raise ValueError(f"Param {name} must be a valid UUID, instead got {type(value)} --> {value}")
            else:
                cls.logger.error(f"Parameter {name} is not required and is being skipped because it has value: {value}")
        return True

    @classmethod
    def _get_history_model(cls, model):
        """
        Return the pghistory Event model for a tracked model.
        """
        for m in apps.get_models():
            if issubclass(m, pghistory.models.Event):
                if getattr(m, "pgh_model", None) is model:
                    return m
        return None

    @classmethod
    def _resolve_lookup_path(cls, root_model, lookup):
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

        if op not in cls.OPS:
            raise ValueError(f"Unsupported operator: {op}")
        
        # 🔥 HANDLE isnull FIRST
        if op == "isnull":
            if value is None:
                value = True  # treat null as IS NULL
            elif not isinstance(value, bool):
                raise ValueError("isnull must be boolean or null")

        # 🔥 THEN skip None for other operators
        elif value is None or (isinstance(value, str) and value.strip() == ""):
            return None

        final_model, lookup = cls._resolve_lookup_path(root_model, field)

        if field.count("__") > cls.MAX_DEPTH:
            raise ValueError("Lookup path too deep")

        django_lookup = field + cls.OPS[op]
        cls.logger.error(f"Django Lookup: {django_lookup}")
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
        cls.logger.error(f"Django Lookup: {django_lookup}")

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
        entity_name = kwargs.get("model_name", None)
        if not isString(entity_name):
            raise ValueError(
                f"Expected model to be a non-empty string, instead got: "
                f"{type(entity_name)} ==> {entity_name}"
            )
        else:
            try:
                base_model = getModelFromName(entity_name)
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
            model_name = query_def.get(cls.model_name_key, None)
            query_ast_def = query_def.get(cls.query_def_key, {})
            return super().run(query_ast_def, params, model_name=model_name, **kwargs)

class FieldDefinitionInterface:

        field_path_key = "path"
        custom_name_key = "name"

        def __init__(self, field_path, custom_name=None):
            if isString(field_path):
                self.field_path = field_path
            else:
                raise ValueError(f"{field_path} is not a valid path to a field")
            if isString(custom_name):
                self.custom_name = custom_name
            else:
                self.custom_name = None

        @classmethod
        def create(cls, **kwargs):
            fp = kwargs.get(cls.field_path_key, None)
            name = kwargs.get(cls.custom_name_key, None)
            try:
                newObj = cls(fp, name)
            except ValueError:
                newObj = None
            except Exception as e:
                cls.logger.error(f"FieldDefinition Create Error: {e}")
                newObj = None
            finally:
                return newObj

class AnnotatedQueryAstHandler(QueryAstHandler):

    path_splitter = "."

    field_def_key = f"query{path_splitter}fields"
    annotate_flag_key = "annotateFlag"

    @classmethod
    def split_fields(cls, field_defs):
        """
        Separates field definitions into:
        - db_fields: handled by ORM (__ paths)
        - virtual_fields: handled in Python (. paths)
        """
        db_fields = []
        virtual_fields = []

        if not isList(field_defs):
            return db_fields, virtual_fields

        for fd in field_defs:
            if not fd or not isString(fd.field_path):
                continue

            if "." in fd.field_path:
                virtual_fields.append(fd)
            else:
                db_fields.append(fd)

        return db_fields, virtual_fields
    
    @classmethod
    def resolve_dot_path(cls, obj, path):
        """
        Resolve dot-notation paths dynamically.

        Supports:
        - party.target.name
        - party.name
        - target.name

        Special keyword:
        - 'target' → resolves GenericForeignKey (content_object)
        """
        if not obj or not isString(path):
            return None

        parts = path.split(".")
        cur = obj

        for part in parts:
            if cur is None:
                return None

            if part == "target":
                cur = getattr(cur, "content_object", None)
            else:
                cur = getattr(cur, part, None)

        return cur
    
    @classmethod
    def normalize_value(cls, value):

        if isinstance(value, Model):
            return str(value)

        if isinstance(value, uuid.UUID):
            return str(value)

        if isinstance(value, (datetime, date)):
            return value.isoformat()

        return value
    
    @classmethod
    def apply_virtual_fields(cls, data, objects, virtual_fields):

        if not isList(data) or not isList(virtual_fields):
            return data

        for row, obj in zip(data, objects):

            if not isinstance(row, dict):
                continue

            for fd in virtual_fields:
                path = fd.field_path
                key = fd.custom_name or path.replace(".", "_")

                row[key] = cls.normalize_value(
                    cls.resolve_dot_path(obj, path)
                )

        return data

    @classmethod
    def find_value_from_path(cls, obj, path):
        if not isString(path):
            cls.logger.error(f"Path is: {type(path)} -> {path}")
            return None
        path_elems = path.split(cls.path_splitter)
        cur = obj
        for p in path_elems:
            cls.logger.error(f"Cur Step: {dictToStr(cur, prefix="\t")}")
            if isDict(cur):
                cur = cur.get(p, None)
            else:
                return None
        return cur

    @classmethod
    def getFields(cls, fields_defs):
        if not isList(fields_defs):
            return None
        fields = []
        for field_def in fields_defs:
            if isDict(field_def):
                cur_def = FieldDefinitionInterface.create(**field_def)
                if cur_def == None:
                    continue
                else:
                    fields.append(cur_def)
            else:
                continue
        return fields
    
    @classmethod
    def build_annotations(cls, field_defs):
        annotations = {}

        for fd in field_defs:
            key = fd.custom_name or fd.field_path.replace("__", "_")
            annotations[key] = F(fd.field_path)

        return annotations

    # 🔥 Extract select_related paths
    @classmethod
    def get_select_related_fields(cls, field_defs):
        related = set()

        for fd in field_defs:
            parts = fd.field_path.split("__")[:-1]
            if parts:
                related.add("__".join(parts))

        return list(related)
    
    @classmethod
    def run(cls, query_def, params={}, **kwargs):
        cls.logger.error(f"Kwargs: {dictToStr(kwargs, prefix="\t")}")
        annotateFlag = kwargs.pop(cls.annotate_flag_key, False)
        cls.logger.error(f"Annonate: {annotateFlag}")
        results = super().run(query_def, params, **kwargs)
        if annotateFlag:
            field_list = cls.getFields(cls.find_value_from_path(query_def, cls.field_def_key))
            cls.logger.error(f"Field List: {type(field_list)} --> {field_list}")
            if not isList(field_list):
                return results
            else:
                db_fields, virtual_fields = cls.split_fields(field_list)
                cls.logger.error(f"DB FIELDS --> {db_fields}")
                cls.logger.error(f"VIRUTAL FIELDS -->{virtual_fields}")
                select_related_fields = cls.get_select_related_fields(db_fields)
                if select_related_fields:
                    results = results.select_related(*select_related_fields)

                # Step 4: annotate fields
                annotations = cls.build_annotations(db_fields)
                cls.logger.error(f"Annotations: {type(annotations)} --> {annotations}")
                if annotations:
                    results = results.annotate(**annotations)
                results._virtual_fields = virtual_fields
                return results
        else:
            return results