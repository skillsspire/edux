from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("app", "0013_quiz_attempts"),
    ]

    operations = [
        migrations.CreateModel(
            name="CertificateRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создано")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлено")),
                ("period_mode", models.CharField(choices=[("with_period", "С периодом обучения"), ("without_period", "Без периода обучения")], max_length=20, verbose_name="Период на сертификате")),
                ("period_start", models.DateField(blank=True, null=True, verbose_name="Дата начала")),
                ("period_end", models.DateField(blank=True, null=True, verbose_name="Дата окончания")),
                ("status", models.CharField(choices=[("pending", "На проверке"), ("issued", "Выдан"), ("rejected", "Отклонён")], default="pending", max_length=20, verbose_name="Статус")),
                ("external_number", models.CharField(blank=True, max_length=100, verbose_name="Номер сертификата")),
                ("pdf_url", models.URLField(blank=True, verbose_name="Ссылка на PDF")),
                ("verify_url", models.URLField(blank=True, verbose_name="Ссылка проверки")),
                ("issued_at", models.DateTimeField(blank=True, null=True, verbose_name="Выдан")),
                ("course", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="certificate_requests", to="app.course", verbose_name="Курс")),
                ("enrollment", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="certificate_request", to="app.enrollment", verbose_name="Зачисление")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="certificate_requests", to=settings.AUTH_USER_MODEL, verbose_name="Пользователь")),
            ],
            options={
                "verbose_name": "Заявка на сертификат",
                "verbose_name_plural": "Заявки на сертификаты",
                "ordering": ["-created_at"],
            },
        ),
    ]
