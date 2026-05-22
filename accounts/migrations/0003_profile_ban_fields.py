from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_profile_premium"),
    ]

    operations = [
        migrations.CreateModel(
            name="FeatureBan",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name="ID",
                    ),
                ),
                (
                    "profile",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="feature_bans",
                        to="accounts.profile",
                    ),
                ),
                (
                    "feature",
                    models.CharField(
                        db_index=True,
                        max_length=50,
                        choices=[
                            ("full_account",           "🚫 Full Account (blocks everything)"),
                            ("regular",                "🤖 Regular Mode"),
                            ("uncensored",             "🔥 Uncensored Mode"),
                            ("ocr",                    "📄 OCR Mode"),
                            ("multi_debugger",         "🔍 Multi-Debugger (all tiers)"),
                            ("multi_debugger_premium", "⭐ Multi-Debugger — Premium Tier Only"),
                        ],
                    ),
                ),
                (
                    "expires_at",
                    models.DateTimeField(
                        blank=True, null=True,
                        help_text="Leave blank for a permanent ban. Set to a future datetime for temporary.",
                    ),
                ),
                (
                    "reason",
                    models.CharField(
                        blank=True, default="", max_length=500,
                        help_text="Shown to the user in the UI.",
                    ),
                ),
                ("banned_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["feature"]},
        ),
        migrations.AlterUniqueTogether(
            name="featureban",
            unique_together={("profile", "feature")},
        ),
    ]
