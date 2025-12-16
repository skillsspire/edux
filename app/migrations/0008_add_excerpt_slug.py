from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('app', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='article',
            name='excerpt',
            field=models.TextField(blank=True, verbose_name='Краткое описание'),
        ),
        migrations.AddField(
            model_name='material',
            name='slug',
            field=models.CharField(blank=True, max_length=220),
        ),
    ]
