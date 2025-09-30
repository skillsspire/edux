from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ("app", "0010_merge_20250929_2243"),
    ]
    operations = [
        migrations.AddField(
            model_name="article",
            name="body",
            field=models.TextField("Текст", blank=True, default=""),
        ),
        migrations.AddField(
            model_name="material",
            name="description",
            field=models.TextField("Описание", blank=True, default=""),
        ),
    ]
