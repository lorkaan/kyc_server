
from kycserver.watchdog.models import Signal, SignalSeverity, SignalType


def create_signal(instance, signal_type_label, **kwargs):
    signal_type, _ = SignalType.objects.get_or_create(label=signal_type_label)    # This is core to the system, so it needs to create if it does not exist
    severity = SignalSeverity.objects.get(code="info")  # or whatever default

    Signal.objects.create(
        signal_type=signal_type,
        severity=severity,
        content_object=instance,  # 👈 Generic FK target
        metadata=kwargs
    )