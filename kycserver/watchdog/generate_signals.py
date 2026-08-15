from django.db import transaction
from watchdog.models import Signal, SignalSeverity, SignalType


@transaction.atomic
def create_signal(*, instance, signal_type_label: str, metadata: dict | None = None, signal_model=None):
    """
    Core signal creation entrypoint.

    This is intentionally simple and stable so all apps can rely on it.
    """

    if not signal_type_label or not signal_type_label.strip():
        raise ValueError("signal_type_label cannot be empty")

    signal_model = signal_model or Signal

    signal_type, _ = SignalType.objects.get_or_create(
        label=signal_type_label.strip()
    )

    signal = signal_model.objects.create(
        signal_type=signal_type,
        content_object=instance,
        metadata=metadata or {}
    )

    return signal