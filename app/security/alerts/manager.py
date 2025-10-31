"""
Back-compat shim: Lütfen import’ları `app.alerts` altına taşıyın.
Bu dosya ileride kaldırılacaktır.
"""
from app.alerts.base import (  # noqa: F401
    AlertManager,
    AlertPayload,
    AlertSink,
    make_payload,
)