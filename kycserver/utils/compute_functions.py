
from django.db.models import Case, Value, When


COMPUTE_OPS = {}

def register_compute_op(name):
    def decorator(func):
        COMPUTE_OPS[name] = func
        return func
    return decorator

@register_compute_op("case")
def compute_case(fd, resolver):
    conditions = fd.compute.get("conditions", [])
    default = fd.compute.get("default")

    whens = []

    for condition in conditions:
        when_clause = condition.get("when", {})
        then_value = condition.get("then")

        # Resolve expressions properly
        resolved_when = {
            key: resolver.resolve_expression(value)
            for key, value in when_clause.items()
        }

        resolved_then = resolver.resolve_expression(then_value)

        whens.append(
            When(**resolved_when, then=resolved_then)
        )

    return Case(
        *whens,
        default=resolver.resolve_expression(default)
    )

@register_compute_op("list")
def compute_list(fd, resolver):
    pass

@register_compute_op("null")
def compute_null(fd, resolver):
    pass