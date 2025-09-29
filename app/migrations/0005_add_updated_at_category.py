from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0004_add_created_at_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="category",
            name="updated_at",
            # заполним существующие строки текущим временем, дальше auto_now будет работать сам
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
    ]
