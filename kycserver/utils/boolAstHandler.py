
import re

from utils.dsl_evaluator import DslEvaluator


class BooleanAstHandler(DslEvaluator):

    OPS = {
        "eq": lambda a, b: a == b,
        "neq": lambda a, b: a != b,
        "lt": lambda a, b: a < b,
        "lte": lambda a, b: a <= b,
        "gt": lambda a, b: a > b,
        "gte": lambda a, b: a >= b,
        "in": lambda a, b: a in (b or []),
        "contains": lambda a, b: b in (a or ""),
        "exists": lambda a, _: a is not None,
        "regex": lambda a, b: bool(re.match(b, str(a or ""))),
    }

    @classmethod
    def evaluate(cls, ast_obj, **kwargs):
        """
        Calls the BooleanLogicEngine with prepared context.
        """
        if ast_obj is None:
            return True

        def _eval(node):

            if node is None:
                return True

            if not isinstance(node, dict):
                raise ValueError(f"Invalid AST node: {node}")

            # AND
            if "and" in node:
                return all(_eval(child) for child in node["and"])

            # OR
            if "or" in node:
                return any(_eval(child) for child in node["or"])

            # NOT
            if "not" in node:
                return not _eval(node["not"])

            # Predicate
            if not {"field", "op"}.issubset(node):
                raise ValueError(f"Invalid predicate node: {node}")

            field = node["field"]
            op = node["op"]
            expected = node.get("value")

            if op not in cls.OPS:
                raise ValueError(f"Unsupported operator: {op}")

            # resolve actual value from kwargs context
            actual = kwargs.get(field)

            return cls.OPS[op](actual, expected)

        return bool(_eval(ast_obj))