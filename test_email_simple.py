import os
import django
from django.conf import settings

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'edux.settings')
django.setup()

from django.core.mail import send_mail

def test_email():
    try:
        send_mail(
            'Тест email от SkillsSpire',
            'Это тестовое письмо! Если вы его получили, настройки работают!',
            'skillsspire@gmail.com',
            ['skillsspire@gmail.com'],
            fail_silently=False,
        )
        print('✅ Email отправлен успешно!')
        return True
    except Exception as e:
        print(f'❌ Ошибка отправки письма: {e}')
        return False

if __name__ == '__main__':
    test_email()