# app/migrations/0008_article_excerpt_and_material_slug.py
from django.db import migrations, models
from django.utils.text import slugify


def fill_material_slugs(apps, schema_editor):
    Material = apps.get_model("app", "Material")
    # Собираем уже занятые слуги, чтобы гарантировать уникальность при генерации
    existing = set(
        Material.objects.exclude(slug__isnull=True).exclude(slug="").values_list("slug", flat=True)
    )

    def unique_slug(title, pk):
        base = (slugify(title)[:200] or f"material-{pk}")
        s = base
        i = 2
        while s in existing:
            s = f"{base}-{i}"
            i += 1
        existing.add(s)
        return s

    for m in Material.objects.all().only("id", "title", "slug"):
        if not m.slug:
            m.slug = unique_slug(m.title or "", m.pk)
            m.save(update_fields=["slug"])


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0007_create_articles_materials"),
    ]

    operations = [
        # 1) Добавляем краткое описание к Article
        migrations.AddField(
            model_name="article",
            name="excerpt",
            field=models.TextField("Краткое описание", blank=True, default=""),
            preserve_default=False,
        ),
        # 2) Временный nullable slug у Material, чтобы можно было заполнить
        migrations.AddField(
            model_name="material",
            name="slug",
            field=models.SlugField("Слаг", max_length=220, blank=True, null=True),
        ),
        # 3) Заполняем slug для существующих записей
        migrations.RunPython(fill_material_slugs, migrations.RunPython.noop),
        # 4) Делаем slug обязательным и уникальным
        migrations.AlterField(
            model_name="material",
            name="slug",
            field=models.SlugField("Слаг", max_length=220, unique=True),
        ),
    ]
