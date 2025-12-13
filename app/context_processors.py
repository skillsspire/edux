def site_settings(request):
    """
    Добавляет глобальные переменные в контекст всех шаблонов
    """
    from django.conf import settings
    
    return {
        'STATIC_VERSION': getattr(settings, 'STATIC_VERSION', '1.0'),
        'SUPABASE_URL': getattr(settings, 'SUPABASE_URL', ''),
        'SUPABASE_ANON_KEY': getattr(settings, 'SUPABASE_ANON_KEY', ''),
        'DEBUG': getattr(settings, 'DEBUG', False),
        'KASPI_PAYMENT_URL': getattr(settings, 'KASPI_PAYMENT_URL', ''),
    }