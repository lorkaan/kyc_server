
from django.db import models
from django.db.models import Q, Case, StringAgg, Value, When
from django.db.models.functions import Cast


COMPUTE_OPS = {}

def register_compute_op(name):
    def decorator(func):
        COMPUTE_OPS[name] = func
        return func
    return decorator

@register_compute_op("case")
def compute_case(defn, resolver, root_model):
    whens = []

    for condition in defn.get("conditions", []):
        when_clause = condition.get("when", {})
        then_value = condition.get("then")

        whens.append(
            When(
                **when_clause,
                then=resolver.resolve_expression(then_value, root_model),
            )
        )

    default = resolver.resolve_expression(
        defn.get("default"), root_model
    )

    return Case(
        *whens,
        default=default,
        output_field=models.CharField(null=True),
    )


@register_compute_op("list")
def compute_list(defn, resolver, root_model):
    value = defn.get("value")
    delimiter = defn.get("delimiter", ", ")
    filters = defn.get("filters")

    expression = resolver.resolve_expression(value, root_model)

    # PostgreSQL STRING_AGG requires a text expression.
    expression = Cast(expression, output_field=models.CharField())

    return StringAgg(
        expression,
        delimiter=delimiter,
        filter=Q(**filters) if filters else None,
        output_field=models.TextField(),
    )

@register_compute_op("null")
def compute_null(defn, resolver, root_model):
    return Value(None, output_field=models.CharField(null=True))

@register_compute_op("literal")
def compute_literal(defn, resolver, root_model):
    return Value(defn.get("value"))