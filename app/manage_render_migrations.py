import os
from django.core.management import call_command
from django.core.wsgi import get_wsgi_application

# Указываем настройки Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "edux.settings")

# Инициализируем Django
application = get_wsgi_application()

# Название твоего приложения (как в settings.py -> INSTALLED_APPS)
apps = ["app"]

# Применяем "фейковые" миграции
for app in apps:
    print(f"Faking migrations for {app}...")
    call_command("migrate", app, fake=True, interactive=False)

print("✅ All migrations faked successfully.")
