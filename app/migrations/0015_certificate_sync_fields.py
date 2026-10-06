from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0014_certificate_request"),
    ]

    operations = [
        migrations.AddField(
            model_name="certificaterequest",
            name="external_request_id",
            field=models.CharField(blank=True, max_length=120, verbose_name="ID заявки во внешней системе"),
        ),
        migrations.AddField(
            model_name="certificaterequest",
            name="synced_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Передано в реестр"),
        ),
        migrations.AddField(
            model_name="certificaterequest",
            name="sync_error",
            field=models.TextField(blank=True, verbose_name="Ошибка синхронизации"),
        ),
    ]
