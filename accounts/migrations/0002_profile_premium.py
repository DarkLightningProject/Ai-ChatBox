from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="is_premium",
            field=models.BooleanField(default=False, db_index=True),
        ),
        migrations.AddField(
            model_name="profile",
            name="premium_granted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
