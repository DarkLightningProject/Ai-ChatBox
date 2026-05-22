from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0004_message_session_fk"),
    ]

    operations = [
        migrations.AddField(
            model_name="message",
            name="agent_data",
            field=models.JSONField(blank=True, default=None, null=True),
        ),
    ]
