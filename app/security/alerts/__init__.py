# DEPRECATED: Bu modül geri-uyumluluk içindir. Yeni import yolu: app.alerts
import warnings
warnings.warn(
    "Import path deprecated: use `from app.alerts import ...` instead of `app.security.alerts`.",
    DeprecationWarning,
    stacklevel=2,
)

from app.alerts import AlertPayload, AlertSink, AlertManager, make_payload

__all__ = [
    "AlertPayload",
    "AlertSink",
    "AlertManager",
    "make_payload",
]