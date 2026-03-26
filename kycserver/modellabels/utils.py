

def get_field_label(model, field_name, override: dict = None) -> str:
    """
    Get a human-readable label for a model field.
    
    :param model: The Django model class
    :param field_name: The field name string, e.g., 'person__name'
    :param override: Optional dict of {field_name: label} to override labels for a query
    :return: Human-readable string
    """
    if override and field_name in override:
        return override[field_name]
    
    from .models import ModelFieldLabel
    from django.contrib.contenttypes.models import ContentType
    
    try:
        # Lookup ModelFieldLabel for this model and field
        content_type = ContentType.objects.get_for_model(model)
        return ModelFieldLabel.objects.get(content_type=content_type, field_name=field_name).label
    except ModelFieldLabel.DoesNotExist:
        # fallback: prettify field name
        return field_name.replace('_', ' ').title()