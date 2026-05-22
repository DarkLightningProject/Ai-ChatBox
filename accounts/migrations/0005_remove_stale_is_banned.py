from django.db import migrations


def drop_is_banned(apps, schema_editor):
    # Drop the index first (SQLite won't drop a column that has an index),
    # then drop the stale column left over from a deleted migration.
    schema_editor.execute(
        "DROP INDEX IF EXISTS accounts_profile_is_banned_a25fb09a"
    )
    schema_editor.execute(
        "ALTER TABLE accounts_profile DROP COLUMN is_banned"
    )


class Migration(migrations.Migration):
    """
    The accounts_profile table has a stale 'is_banned' column (with an index)
    left over from a previous migration that was deleted. The column is no
    longer in the model and its NOT NULL constraint breaks profile creation.
    """

    dependencies = [
        ("accounts", "0004_alter_featureban_id"),
    ]

    operations = [
        migrations.RunPython(drop_is_banned, migrations.RunPython.noop),
    ]
