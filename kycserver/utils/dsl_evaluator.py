from copy import deepcopy
from globalparams.models import GlobalParameter
from utils.dict_utils import dictToStr, isDict
from utils.type_utils import isString
import logging

class DslEvaluator:

    global_param_key = "global_params"
    param_key = "params"

    local_param_key = "$param"

    logical_nodes = ["and", "or"]

    eval_statement_key = ""

    key_path_sep = "."

    logger = logging.getLogger()

    @classmethod
    def validate_params(cls, param_def: dict, params: dict):
        return True

    @classmethod
    def bind_params(cls, ast, params: dict):
        """
        Replace {$param: name} nodes with concrete values.
        Optional params not provided are removed.
        Also prunes empty logical nodes (and/or) recursively.
        Returns a NEW AST (does not mutate input).
        """
        ast = deepcopy(ast)

        def _bind(node):
            if isinstance(node, dict):
                # Parameter reference
                if cls.local_param_key in node:
                    name = node[cls.local_param_key]
                    return params.get(name)  # None if missing optional

                # Recursive binding
                bound = {k: _bind(v) for k, v in node.items()}
                # Remove None values
                bound = {k: v for k, v in bound.items() if v is not None}

                # Prune empty logical nodes
                for logical_op in cls.logical_nodes:
                    if logical_op in bound and not bound[logical_op]:
                        return None

                return bound if bound else None

            elif isinstance(node, list):
                bound_list = [_bind(v) for v in node]
                bound_list = [v for v in bound_list if v is not None]
                return bound_list if bound_list else None

            return node  # scalar

        return _bind(ast)

    @classmethod
    def _resolve_global_params(cls, global_param_map={}):
        """
        Resolves global parameters defined in query_def["global_param"].
        Returns a dict mapping query parameter names to their resolved values.
        Each value is type-safe via GlobalParameter.get_value().
        """
        resolved = {}

        if not isDict(global_param_map, nonEmpty=False):
            return resolved  # No global params

        # Fetch active global parameters from DB
        gp_names = list(global_param_map.values())
        global_params_qs = GlobalParameter.objects.filter(
            name__in=gp_names,
            is_active=True
        )

        for gp in global_params_qs:
            # Find the param name in the query that maps to this global parameter
            # (reverse lookup from query global_param mapping)
            param_names = [k for k, v in global_param_map.items() if v == gp.name]
            if not param_names:
                continue  # safety: shouldn't happen
            param_name = param_names[0]

            # Use get_value() for type-safe resolution
            resolved[param_name] = gp.get_value()

        return resolved
    
    @classmethod
    def resolve_parameters(cls, param_def={}, global_param_def={}, params={}):
        if not isDict(global_param_def, nonEmpty=False):
            raise ValueError(f"Expected Global Parameter Definition to be a dictionary, instead got: {type(global_param_def)}")
        if not isDict(param_def, nonEmpty=False):
            raise ValueError(f"Expected Parameter Definition to be a dictionary, instead got: {type(param_def)}")
        resolved_params = {}
        #global_param_def = query_def.get("global_params")
        if isDict(global_param_def):
            cls.validate_params(global_param_def, params)
            resolved_params.update(cls._resolve_global_params(global_param_def))

        # ---- Params handling ----
        #param_def = query_def.get("params")
        if isDict(param_def):
            cls.validate_params(param_def, params)
            resolved_params.update(params)
        return resolved_params

    
    @classmethod
    def get_eval_statement(cls, eval_block):
        if not isDict(eval_block):
             raise TypeError(f"Eval Block is not a dictionary: {type(eval_block)}")
        elif isString(cls.eval_statement_key):
            key_path = cls.eval_statement_key.split(cls.key_path_sep)
            eval_statement = eval_block
            for path in key_path:
                cls.logger.error(f"Checking {path} in {key_path}")
                if isDict(eval_statement, keys=[path]):
                    cls.logger.error(f"Before {path} in {dictToStr(eval_statement, prefix="\t")}")
                    eval_statement = eval_statement.get(path, {})
                    cls.logger.error(f"After {path} in {dictToStr(eval_statement, prefix="\t")}")
                else:
                    raise ValueError(f"Using the key path: {cls.eval_statement_key}\n\tExpected a Dictionary, got: {type(eval_statement)} that looks like:\n{dictToStr(eval_statement, prefix="\t")}\n\tExpected path to be non-empty string: {path}")
            if eval_statement is not None and not isDict(eval_statement):
                raise ValueError(f"Expected \"{cls.eval_statement_key}\" to be a dictionary, got {type(eval_statement)}")
            else:
                return eval_statement
        else:
            return eval_block
        
    @classmethod
    def fill(cls, query_def, params={}):
        eval_statement = cls.get_eval_statement(query_def)
        cls.logger.error(f"Eval Statement: \n{dictToStr(eval_statement, prefix="\t")}")
        resolved_params = cls.resolve_parameters(query_def.get(cls.param_key) or {}, query_def.get(cls.global_param_key) or {}, params)
        cls.logger.error(f"Resolved Params: \n{dictToStr(resolved_params, prefix="\t")}")
        return cls.bind_params(eval_statement, resolved_params)
    
    @classmethod
    def evaluate(cls, ast_obj, **kwargs):
        return None
    
    @classmethod
    def run(cls, query_def, params={}, **kwargs):
        ast_obj = cls.fill(query_def, params)
        return cls.evaluate(ast_obj)