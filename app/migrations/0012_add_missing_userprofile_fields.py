from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0011_alter_userprofile_platform_role"),
    ]

    # The fields is_deleted/deleted_at are already part of the historical
    # 0001 state in this repository. The old 0012 attempted to add them a
    # second time, which made a clean database impossible to migrate.
    operations = []
