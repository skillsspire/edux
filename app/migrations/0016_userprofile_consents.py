from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0015_certificate_sync_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="offer_accepted_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Оферта принята"),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="privacy_accepted_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Согласие на обработку ПД"),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="offer_version",
            field=models.CharField(blank=True, max_length=50, verbose_name="Версия оферты"),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="privacy_version",
            field=models.CharField(blank=True, max_length=50, verbose_name="Версия согласия"),
        ),
    ]
