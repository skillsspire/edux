from django.conf import settings

def kaspi(request):
    return {
        "KASPI_PAYMENT_URL": getattr(settings, "KASPI_PAYMENT_URL", ""),
    }
