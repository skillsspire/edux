from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("app", "0012_add_missing_userprofile_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="quiz",
            name="unlimited_attempts",
            field=models.BooleanField(
                default=False,
                help_text="Если включено, числовое ограничение attempts_allowed не применяется.",
                verbose_name="Неограниченные попытки",
            ),
        ),
        migrations.CreateModel(
            name="QuizAttempt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("attempt_number", models.PositiveIntegerField(default=1, verbose_name="Номер попытки")),
                ("score_percent", models.PositiveIntegerField(default=0, verbose_name="Результат, %")),
                ("points_earned", models.PositiveIntegerField(default=0, verbose_name="Набрано баллов")),
                ("points_total", models.PositiveIntegerField(default=0, verbose_name="Всего баллов")),
                ("passed", models.BooleanField(default=False, verbose_name="Пройден")),
                ("answers", models.JSONField(blank=True, default=dict, verbose_name="Ответы")),
                ("completed_at", models.DateTimeField(auto_now_add=True, verbose_name="Завершена")),
                ("quiz", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attempts", to="app.quiz", verbose_name="Тест")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="quiz_attempts", to=settings.AUTH_USER_MODEL, verbose_name="Пользователь")),
            ],
            options={
                "verbose_name": "Попытка теста",
                "verbose_name_plural": "Попытки тестов",
                "ordering": ["-completed_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="quizattempt",
            index=models.Index(fields=["user", "quiz"], name="app_quizatt_user_id_72f4cb_idx"),
        ),
        migrations.AddIndex(
            model_name="quizattempt",
            index=models.Index(fields=["quiz", "passed"], name="app_quizatt_quiz_id_d68487_idx"),
        ),
    ]
