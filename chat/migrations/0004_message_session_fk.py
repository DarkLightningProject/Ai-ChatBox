import django.db.models.deletion
from django.db import migrations, models


def delete_orphan_messages(apps, schema_editor):
    """Remove messages whose session_id has no matching ChatSession."""
    Message = apps.get_model("chat", "Message")
    ChatSession = apps.get_model("chat", "ChatSession")
    valid_ids = ChatSession.objects.values_list("session_id", flat=True)
    Message.objects.exclude(session_id__in=valid_ids).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0003_chatsession_user"),
    ]

    operations = [
        # 1. Delete orphans first so the FK constraint won't fail
        migrations.RunPython(delete_orphan_messages, migrations.RunPython.noop),

        # 2. Replace the raw CharField with a real ForeignKey
        #    db_column='session_id' keeps the same physical column name,
        #    so no data is moved and existing rows are valid immediately.
        migrations.AlterField(
            model_name="message",
            name="session_id",
            field=models.ForeignKey(
                db_column="session_id",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="messages",
                to="chat.chatsession",
                to_field="session_id",
            ),
        ),
    ]
