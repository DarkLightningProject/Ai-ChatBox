# accounts/models.py

from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


FEATURE_CHOICES = [
    ("full_account",           "🚫 Full Account (blocks everything)"),
    ("regular",                "🤖 Regular Mode"),
    ("uncensored",             "🔥 Uncensored Mode"),
    ("ocr",                    "📄 OCR Mode"),
    ("multi_debugger",         "🔍 Multi-Debugger (all tiers)"),
    ("multi_debugger_premium", "⭐ Multi-Debugger — Premium Tier Only"),
]

FEATURE_LABELS = dict(FEATURE_CHOICES)


class Profile(models.Model):
    """
    Optional user profile.
    Safe: does NOT affect existing chat models.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    email_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    # Premium access
    is_premium = models.BooleanField(default=False, db_index=True)
    premium_granted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.user.username

    def get_active_bans(self):
        """
        Returns {feature: FeatureBan} for all currently active bans.
        Auto-deletes expired rows so the admin never sees stale data.
        """
        from django.utils import timezone
        now       = timezone.now()
        result    = {}
        to_delete = []
        for ban in self.feature_bans.all():
            if ban.expires_at is not None and now >= ban.expires_at:
                to_delete.append(ban.pk)
            else:
                result[ban.feature] = ban
        if to_delete:
            FeatureBan.objects.filter(pk__in=to_delete).delete()
        return result

    def is_feature_banned(self, feature, tier=None):
        """True if the given feature+tier combo is actively banned."""
        active = self.get_active_bans()
        if "full_account" in active:
            return True
        if feature in active:
            return True
        # Premium-only ban blocks premium tier of multi_debugger
        if (
            feature == "multi_debugger"
            and tier == "premium"
            and "multi_debugger_premium" in active
        ):
            return True
        return False


class FeatureBan(models.Model):
    """
    Per-feature ban entry. One row per (profile, feature) pair.
    Use update_or_create when applying a ban so duration can be updated.
    """
    profile = models.ForeignKey(
        Profile, related_name="feature_bans", on_delete=models.CASCADE
    )
    feature = models.CharField(
        max_length=50, choices=FEATURE_CHOICES, db_index=True
    )
    expires_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Leave blank for a permanent ban. Set to a future datetime for temporary.",
    )
    reason = models.CharField(
        max_length=500, blank=True, default="",
        help_text="Shown to the user in the UI.",
    )
    banned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("profile", "feature")]
        ordering = ["feature"]

    def __str__(self):
        label = FEATURE_LABELS.get(self.feature, self.feature)
        expiry = self.expires_at.strftime("%Y-%m-%d") if self.expires_at else "permanent"
        return f"{self.profile.user.username} — {label} ({expiry})"

    @property
    def is_active(self):
        if self.expires_at is None:
            return True
        from django.utils import timezone
        return timezone.now() < self.expires_at


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user=instance)
