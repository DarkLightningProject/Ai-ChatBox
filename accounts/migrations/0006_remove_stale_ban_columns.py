from django.db import migrations


def drop_stale_ban_columns(apps, schema_editor):
    db = schema_editor.connection
    columns = [col.name for col in db.introspection.get_table_description(db.cursor(), "accounts_profile")]
    for col in ("ban_expires_at", "ban_reason", "banned_at"):
        if col in columns:
            schema_editor.execute(
                f"ALTER TABLE accounts_profile DROP COLUMN {col}"
            )


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_remove_stale_is_banned"),
    ]

    operations = [
        migrations.RunPython(drop_stale_ban_columns, migrations.RunPython.noop),
    ]
