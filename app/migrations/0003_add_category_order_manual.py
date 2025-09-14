from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('app', '0002_add_is_active_manual'),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='order',
            field=models.PositiveIntegerField(default=0, verbose_name='Порядок'),
        ),
        migrations.AddIndex(
            model_name='category',
            index=models.Index(fields=['order'], name='app_category_order_idx'),
        ),
    ]
