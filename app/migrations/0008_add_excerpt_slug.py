from django.db import migrations, models
from django.utils.text import slugify


def backfill_material_slugs(apps, schema_editor):
    Material = apps.get_model("app", "Material")
    qs = Material.objects.using(schema_editor.connection.alias).all()
    for m in qs:
        if not getattr(m, "slug", None):
            base = (slugify(m.title) or f"material-{m.pk}")[:200]
            slug = base
            i = 2
            while Material.objects.using(schema_editor.connection.alias).filter(slug=slug).exclude(pk=m.pk).exists():
                suffix = f"-{i}"
                slug = (base[:220 - len(suffix)] + suffix)
                i += 1
            m.slug = slug
            m.save(update_fields=["slug"])


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0007_create_articles_materials"),
    ]

    operations = [
        migrations.RunSQL(
            "DROP INDEX IF EXISTS app_material_slug_c087ef9f_like;",
            reverse_sql="",
        ),
        migrations.AddField(
            model_name="article",
            name="excerpt",
            field=models.TextField("Краткое описание", blank=True),
        ),
        migrations.AddField(
            model_name="material",
            name="slug",
            field=models.SlugField("Слаг", max_length=220, unique=True, blank=True, null=True),
        ),
        migrations.RunPython(backfill_material_slugs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="material",
            name="slug",
            field=models.SlugField("Слаг", max_length=220, unique=True, blank=True),
        ),
    ]
