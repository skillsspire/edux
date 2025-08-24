from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings

class Command(BaseCommand):
    help = 'Test email sending configuration'

    def handle(self, *args, **options):
        try:
            send_mail(
                'Тестовое письмо от SkillsSpire',
                'Это тестовое письмо для проверки настроек email.\n\nЕсли вы получили это письмо, значит настройки работают правильно!',
                settings.DEFAULT_FROM_EMAIL,
                ['skillsspire@gmail.com'],  # отправьте себе
                fail_silently=False,
            )
            self.stdout.write(
                self.style.SUCCESS('✅ Тестовое письмо отправлено успешно!')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Ошибка отправки письма: {str(e)}')
            )