
from django.db.models import Case, StringAgg, Value, When


COMPUTE_OPS = {}

def register_compute_op(name):
    def decorator(func):
        COMPUTE_OPS[name] = func
        return func
    return decorator

@register_compute_op("case")
def compute_case(defn, resolver, root_model):
    conditions = defn.get("conditions", [])
    default = defn.get("default")

    whens = []

    for condition in conditions:
        when_clause = condition.get("when", {})
        then_value = condition.get("then")

        resolved_when = {
            key: resolver.resolve_expression(value, root_model)
            for key, value in when_clause.items()
        }

        resolved_then = resolver.resolve_expression(then_value, root_model)

        whens.append(
            When(**resolved_when, then=resolved_then)
        )

    return Case(
        *whens,
        default=resolver.resolve_expression(default, root_model)
    )

@register_compute_op("list")
def compute_list(defn, resolver, root_model):
    value = defn.get("value")
    delimiter = defn.get("delimiter", ", ")

    expression = resolver.resolve_expression(
        value,
        root_model,
    )

    return StringAgg(
        expression,
        delimiter=delimiter,
    )

@register_compute_op("null")
def compute_null(defn, resolver, root_model):
    return Value(None)

@register_compute_op("literal")
def compute_literal(defn, resolver, root_model):
    return Value(defn.get("value"))