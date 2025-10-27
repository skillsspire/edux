from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('app', '0003_add_view_count'),
    ]

    operations = [
        migrations.AddField(
            model_name='material',
            name='download_count',
            field=models.IntegerField(default=0),
        ),
    ]
