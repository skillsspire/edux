from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0009_remove_article_author_alter_material_slug'),
    ]

    # UserProfile.platform_role is already present in the repository's
    # 0001_initial migration. The historical AddField would therefore
    # duplicate the column on a clean PostgreSQL database.
    operations = []
