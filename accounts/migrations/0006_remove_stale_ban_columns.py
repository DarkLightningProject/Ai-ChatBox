from django.db import migrations


def drop_stale_ban_columns(apps, schema_editor):
    # These three columns are leftovers from a deleted migration that stored
    # ban data directly on Profile. They are now replaced by the FeatureBan
    # model but were never removed from the database.
    for col in ("ban_expires_at", "ban_reason", "banned_at"):
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
