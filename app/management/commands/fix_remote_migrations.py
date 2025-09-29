# app/management/commands/fix_remote_migrations.py
from django.core.management.base import BaseCommand
from django.db import connection

SQL = """
ALTER TABLE IF EXISTS app_article  ADD COLUMN IF NOT EXISTS excerpt text;
ALTER TABLE IF EXISTS app_material ADD COLUMN IF NOT EXISTS slug varchar(220);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE c.relname='app_material_slug_c087ef9f_like'
  ) THEN
    CREATE INDEX app_material_slug_c087ef9f_like
      ON app_material (slug text_pattern_ops);
  END IF;
END$$;

INSERT INTO django_migrations (app, name, applied)
SELECT 'app','0008_add_excerpt_slug', NOW()
WHERE NOT EXISTS (
  SELECT 1 FROM django_migrations WHERE app='app' AND name='0008_add_excerpt_slug'
);
"""

class Command(BaseCommand):
    help = "One-off fix: ensure columns/index and mark app.0008 as applied on remote DB."

    def handle(self, *args, **kwargs):
        with connection.cursor() as c:
            for stmt in [s.strip() for s in SQL.split(";\n\n") if s.strip()]:
                c.execute(stmt if stmt.endswith(";") else stmt + ";")
        self.stdout.write(self.style.SUCCESS("fix_remote_migrations: done"))
