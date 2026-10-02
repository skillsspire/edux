import json
import logging
import urllib.error
import urllib.request

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class CertificateRegistryError(Exception):
    pass


def build_certificate_payload(cert_request):
    enrollment = cert_request.enrollment
    user = cert_request.user
    course = cert_request.course

    surname = (user.last_name or "").strip()
    name = (user.first_name or "").strip()
    full_name = (user.get_full_name() or user.username or user.email or "").strip()

    if cert_request.period_mode == cert_request.WITH_PERIOD:
        start_date = cert_request.period_start.isoformat() if cert_request.period_start else ""
        end_date = cert_request.period_end.isoformat() if cert_request.period_end else ""
    else:
        start_date = ""
        end_date = ""

    return {
        "source": "skillsspire_site",
        "local_request_id": str(cert_request.pk),
        "language": "Русский",
        "surname": surname,
        "name": name,
        "full_name": full_name,
        "email": user.email or "",
        "course": course.title,
        "hours": int(course.duration_hours or 0),
        "period_mode": cert_request.period_mode,
        "start_date": start_date,
        "end_date": end_date,
        "completed_at": enrollment.completed_at.isoformat() if enrollment.completed_at else "",
        "enrolled_at": enrollment.enrolled_at.isoformat() if enrollment.enrolled_at else "",
    }


def sync_certificate_request(cert_request, timeout=12):
    endpoint = getattr(settings, "CERTIFICATE_REGISTRY_ENDPOINT", "").strip()
    token = getattr(settings, "CERTIFICATE_REGISTRY_TOKEN", "").strip()

    if not endpoint:
        raise CertificateRegistryError("Не задан CERTIFICATE_REGISTRY_ENDPOINT.")

    payload = build_certificate_payload(cert_request)
    if token:
        payload["token"] = token

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise CertificateRegistryError(str(exc)) from exc

    try:
        result = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        raise CertificateRegistryError("Реестр вернул некорректный JSON.") from exc

    if not result.get("ok"):
        raise CertificateRegistryError(result.get("error") or "Реестр отклонил заявку.")

    cert_request.external_request_id = str(result.get("request_id") or "")
    cert_request.synced_at = timezone.now()
    cert_request.sync_error = ""
    cert_request.save(update_fields=["external_request_id", "synced_at", "sync_error", "updated_at"])
    return result
