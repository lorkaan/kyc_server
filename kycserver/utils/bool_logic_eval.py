import datetime
import re


class BooleanLogicEngine:

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

    # -----------------------------
    # Public API
    # -----------------------------

    @classmethod
    def eval(cls, rule, ctx):
        """
        ctx = {
            "single": {...},
            "groups": {
                "group_key": [ {...}, {...} ]
            }
        }
        """

        if rule is None:
            return True

        # Group quantifiers
        if "group" in rule:
            return cls._eval_group(rule, ctx)

        # Boolean logic
        if "and" in rule:
            return all(cls.eval(r, ctx) for r in rule["and"])

        if "or" in rule:
            return any(cls.eval(r, ctx) for r in rule["or"])

        if "not" in rule:
            return not cls.eval(rule["not"], ctx)

        # Field predicate
        return cls._eval_predicate(rule, ctx["single"])


    # -----------------------------
    # Group evaluation
    # -----------------------------

    @classmethod
    def _eval_group(cls, rule, ctx):

        group_key = rule["group"]

        rows = ctx.get("groups", {}).get(group_key, [])

        # Empty group handling (compliance-safe defaults)
        if not rows:
            if "none" in rule:
                return True
            return False

        if "any" in rule:
            return any(
                cls.eval(rule["any"], {"single": row, "groups": {}})
                for row in rows
            )

        if "all" in rule:
            return all(
                cls.eval(rule["all"], {"single": row, "groups": {}})
                for row in rows
            )

        if "none" in rule:
            return not any(
                cls.eval(rule["none"], {"single": row, "groups": {}})
                for row in rows
            )

        raise ValueError("Group rule must contain any/all/none")


    # -----------------------------
    # Predicate evaluation
    # -----------------------------

    @classmethod
    def _eval_predicate(cls, rule, ctx):

        if not {"field", "op"}.issubset(rule):
            raise ValueError(f"Invalid predicate: {rule}")

        field = rule["field"]
        op = rule["op"]
        expected = rule.get("value")

        actual = ctx.get(field)

        if op not in cls.OPS:
            raise ValueError(f"Unsupported op: {op}")

        # Auto-parse ISO dates
        expected = cls._coerce_date(expected)
        actual = cls._coerce_date(actual)

        return cls.OPS[op](actual, expected)


    # -----------------------------
    # Utilities
    # -----------------------------

    @staticmethod
    def _coerce_date(value):

        if not isinstance(value, str):
            return value

        try:
            return datetime.date.fromisoformat(value)
        except Exception:
            return value