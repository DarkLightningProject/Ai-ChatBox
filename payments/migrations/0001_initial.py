from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Order",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                (
                    "order_id",
                    models.CharField(db_index=True, max_length=100, unique=True),
                ),
                (
                    "razorpay_payment_id",
                    models.CharField(blank=True, max_length=100, null=True),
                ),
                ("amount", models.PositiveIntegerField()),
                ("currency", models.CharField(default="INR", max_length=10)),
                ("receipt", models.CharField(max_length=100)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("created", "Created"),
                            ("payment_initiated", "Payment Initiated"),
                            ("captured", "Captured"),
                            ("failed", "Failed"),
                        ],
                        db_index=True,
                        default="created",
                        max_length=30,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="orders",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
