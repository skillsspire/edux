from django.db import migrations, models
from django.utils import timezone

class Migration(migrations.Migration):

    dependencies = [
        ('app', '0005_add_updated_at_category'),
    ]

    operations = [
        # 1) Добавляем created_at в wishlist без интерактива
        migrations.AddField(
            model_name='wishlist',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=timezone.now),
            preserve_default=False,
        ),

        # 2) Заполняем NULL в kaspi_invoice_id уникальными значениями
        migrations.RunSQL(
            sql="""
                UPDATE app_payment
                SET kaspi_invoice_id = 'QR-LEGACY-' || id
                WHERE kaspi_invoice_id IS NULL;
            """,
            reverse_sql="""
                UPDATE app_payment
                SET kaspi_invoice_id = NULL
                WHERE kaspi_invoice_id LIKE 'QR-LEGACY-%';
            """,
        ),
    ]
