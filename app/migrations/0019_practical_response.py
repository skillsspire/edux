from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("app", "0018_sync_model_state"),
    ]

    operations = [
        migrations.CreateModel(
            name="PracticalResponse",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создано")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлено")),
                ("text", models.TextField(verbose_name="Ответ")),
                ("block", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="practical_responses", to="app.lessonblock", verbose_name="Практическое задание")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="practical_responses", to=settings.AUTH_USER_MODEL, verbose_name="Пользователь")),
            ],
            options={
                "verbose_name": "Ответ на практическое задание",
                "verbose_name_plural": "Ответы на практические задания",
            },
        ),
        migrations.AddIndex(
            model_name="practicalresponse",
            index=models.Index(fields=["user", "block"], name="pract_resp_user_block_idx"),
        ),
        migrations.AddConstraint(
            model_name="practicalresponse",
            constraint=models.UniqueConstraint(fields=("user", "block"), name="uniq_practical_response_user_block"),
        ),
    ]
