from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0001_initial'),
    ]

    # The current 0001_initial already contains Article.excerpt and Material.slug.
    # Keeping the historical AddField operations would make a clean PostgreSQL
    # install fail with DuplicateColumn. Existing databases that already recorded
    # 0008 as applied are unaffected by making this migration a compatibility no-op.
    operations = []
