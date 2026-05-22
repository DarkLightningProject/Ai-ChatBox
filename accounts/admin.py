from datetime import timedelta

from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.core.cache import cache
from django.utils import timezone
from django.utils.html import format_html, mark_safe

from .models import Profile, FeatureBan, FEATURE_CHOICES, FEATURE_LABELS


def _invalidate_ban_cache_for_profiles(profiles_qs):
    """Clear the per-user ban cache for every affected profile."""
    for uid in profiles_qs.values_list("user_id", flat=True):
        cache.delete(f"bans:{uid}")


# ─── Site branding ────────────────────────────────────────────────────────────

admin.site.site_header = "Conversa Administration"
admin.site.site_title  = "Conversa Admin"
admin.site.index_title = "Control Panel"


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _feature_short_label(feature_key):
    """Return a short, emoji-free label for a feature key (for compact displays)."""
    return (
        FEATURE_LABELS.get(feature_key, feature_key)
        .split("(")[0].strip()
        .lstrip("🚫🤖🔥📄🔍⭐").strip()
    )


def _render_ban_status(ban):
    """Shared HTML renderer for a FeatureBan's time-remaining status."""
    if ban.expires_at is None:
        return format_html('<b style="color:#dc2626;">Permanent</b>')
    remaining = ban.expires_at - timezone.now()
    if remaining.total_seconds() <= 0:
        return format_html('<span style="color:#f59e0b;">Expired (will auto-remove)</span>')
    d = remaining.days
    if d == 0:
        h = int(remaining.seconds // 3600)
        return format_html('<span style="color:#dc2626;">{}h left</span>', h)
    return format_html(
        '<span style="color:#dc2626;">{} day{} left</span>',
        d, "s" if d != 1 else "",
    )

def _apply_bans(profiles_qs, features, days, reason):
    """
    Upsert FeatureBan rows for the given features on every profile.
    days=None → permanent. Also revokes premium when full_account is banned.
    Returns count of affected profiles.
    """
    now     = timezone.now()
    expires = (now + timedelta(days=days)) if days is not None else None
    reason  = (reason or "").strip() or "Violation of terms of service"
    count   = 0
    for profile in profiles_qs:
        for feature in features:
            FeatureBan.objects.update_or_create(
                profile=profile,
                feature=feature,
                defaults={"expires_at": expires, "reason": reason},
            )
        if "full_account" in features:
            profile.is_premium         = False
            profile.premium_granted_at = None
            profile.save(update_fields=["is_premium", "premium_granted_at"])
        cache.delete(f"bans:{profile.user_id}")   # invalidate cached ban list
        count += 1
    return count


def _remove_bans(profiles_qs, features=None):
    """Remove specific feature bans (or all bans if features is None/empty)."""
    _invalidate_ban_cache_for_profiles(profiles_qs)   # clear cache before delete
    qs = FeatureBan.objects.filter(profile__in=profiles_qs)
    if features:
        qs = qs.filter(feature__in=features)
    deleted, _ = qs.delete()
    return deleted


# ─── Admin forms ─────────────────────────────────────────────────────────────

DURATION_CHOICES = [
    ("1",         "1 Day"),
    ("2",         "2 Days"),
    ("3",         "3 Days"),
    ("7",         "7 Days"),
    ("14",        "14 Days"),
    ("30",        "30 Days"),
    ("custom",    "Custom (enter days below)"),
    ("permanent", "Permanent"),
]


class BanUsersForm(forms.Form):
    features = forms.MultipleChoiceField(
        choices=FEATURE_CHOICES,
        label="Features / Modes to ban",
        widget=forms.CheckboxSelectMultiple,
        help_text=(
            "Select one or more features to restrict. "
            "Choosing 'Full Account' blocks the user entirely and revokes premium."
        ),
    )
    duration = forms.ChoiceField(
        choices=DURATION_CHOICES,
        label="Duration",
        initial="3",
        widget=forms.Select(attrs={"class": "vTextField"}),
    )
    custom_days = forms.IntegerField(
        required=False, min_value=1, max_value=3650,
        label="Custom days (only if 'Custom' selected above)",
        widget=forms.NumberInput(attrs={"class": "vTextField"}),
    )
    reason = forms.CharField(
        required=False, max_length=500,
        label="Reason shown to user",
        widget=forms.Textarea(attrs={"rows": 3, "class": "vLargeTextField"}),
        initial="Violation of terms of service",
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("duration") == "custom" and not cleaned.get("custom_days"):
            raise forms.ValidationError(
                "Please enter the number of days when 'Custom' is selected."
            )
        return cleaned


# ─── Inlines ─────────────────────────────────────────────────────────────────

class FeatureBanInline(admin.TabularInline):
    model            = FeatureBan
    extra            = 0          # no blank rows — avoids unique_together confusion
    show_change_link = True
    verbose_name     = "Active Ban"
    verbose_name_plural = "Active Bans (edit or delete individual rows here)"
    fields           = ("feature", "expires_at", "reason", "banned_at", "status_col")
    readonly_fields  = ("banned_at", "status_col")

    def status_col(self, obj):
        if not obj.pk:
            return "—"
        return _render_ban_status(obj)
    status_col.short_description = "Status"


class ProfileInline(admin.StackedInline):
    model               = Profile
    can_delete          = False
    verbose_name_plural = "Profile & Premium"
    fields              = ("is_premium", "premium_granted_at", "email_verified", "created_at")
    readonly_fields     = ("created_at", "premium_granted_at")

    def save_model(self, request, obj, form, change):
        if obj.is_premium and not obj.premium_granted_at:
            obj.premium_granted_at = timezone.now()
        elif not obj.is_premium:
            obj.premium_granted_at = None
        super().save_model(request, obj, form, change)


# ─── User admin ───────────────────────────────────────────────────────────────

class UserAdmin(BaseUserAdmin):
    inlines      = (ProfileInline,)

    def save_formset(self, request, form, formset, change):
        """
        When creating a new user the post_save signal already creates a Profile
        with defaults. The inline would then attempt a second INSERT and hit the
        UNIQUE constraint on accounts_profile.user_id.
        Use update_or_create so the inline's values are applied to whichever
        Profile row exists (signal-created or brand-new).
        """
        if formset.model is Profile:
            instances = formset.save(commit=False)
            for obj in instances:
                # Mirror the premium-timestamp logic from ProfileInline.save_model
                if obj.is_premium and not obj.premium_granted_at:
                    obj.premium_granted_at = timezone.now()
                elif not obj.is_premium:
                    obj.premium_granted_at = None
                Profile.objects.update_or_create(
                    user=obj.user,
                    defaults={
                        "is_premium":         obj.is_premium,
                        "email_verified":     obj.email_verified,
                        "premium_granted_at": obj.premium_granted_at,
                    },
                )
            return
        super().save_formset(request, form, formset, change)

    list_display = (
        "username", "email", "premium_col", "ban_col",
        "is_staff", "is_active", "date_joined",
    )
    list_filter  = BaseUserAdmin.list_filter + ("profile__is_premium",)
    list_per_page = 30

    def premium_col(self, obj):
        try:
            if obj.profile.is_premium:
                return format_html(
                    '<span style="color:#16a34a;font-weight:700;">★ Premium</span>'
                )
            return format_html('<span style="color:#6b7280;">Free</span>')
        except Profile.DoesNotExist:
            return "—"
    premium_col.short_description = "Plan"

    def ban_col(self, obj):
        try:
            active = obj.profile.get_active_bans()
        except Profile.DoesNotExist:
            return "—"
        if not active:
            return format_html('<span style="color:#16a34a;">✓ Active</span>')
        if "full_account" in active:
            return format_html(
                '<span style="color:#dc2626;font-weight:700;">⛔ Full Ban</span>'
            )
        names = [_feature_short_label(f) for f in active]
        return format_html(
            '<span style="color:#f59e0b;font-weight:700;">⚠ {}</span>',
            ", ".join(names),
        )
    ban_col.short_description = "Ban Status"


admin.site.unregister(User)
admin.site.register(User, UserAdmin)


# ─── FeatureBan standalone admin ─────────────────────────────────────────────

@admin.register(FeatureBan)
class FeatureBanAdmin(admin.ModelAdmin):
    list_display  = (
        "username_col", "email_col", "feature_col",
        "status_col", "reason_short", "expires_at", "banned_at",
    )
    list_filter   = ("feature",)
    search_fields = ("profile__user__username", "profile__user__email", "reason")
    ordering      = ("profile__user__username", "feature")
    list_per_page = 50
    # Admins can edit/delete individual bans directly from this view
    fields        = ("profile", "feature", "expires_at", "reason")
    readonly_fields = ("banned_at",)

    def username_col(self, obj):
        return obj.profile.user.username
    username_col.short_description = "Username"
    username_col.admin_order_field = "profile__user__username"

    def email_col(self, obj):
        return obj.profile.user.email
    email_col.short_description = "Email"
    email_col.admin_order_field = "profile__user__email"

    def feature_col(self, obj):
        return FEATURE_LABELS.get(obj.feature, obj.feature)
    feature_col.short_description = "Feature"
    feature_col.admin_order_field = "feature"

    def status_col(self, obj):
        return _render_ban_status(obj)
    status_col.short_description = "Status"

    def reason_short(self, obj):
        if not obj.reason:
            return "—"
        return obj.reason[:60] + ("…" if len(obj.reason) > 60 else "")
    reason_short.short_description = "Reason"


# ─── Profile admin (main ban control panel) ──────────────────────────────────

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    inlines       = [FeatureBanInline]
    list_display  = (
        "username_col", "email_col", "premium_col",
        "ban_summary_col", "email_verified", "created_at",
    )
    list_filter          = ("is_premium", "email_verified", "feature_bans__feature")
    search_fields        = ("user__username", "user__email")
    readonly_fields      = ("created_at", "premium_granted_at", "active_bans_display")
    ordering             = ("-created_at",)
    list_per_page        = 30
    # Fetch user + all feature_bans in 2 queries total instead of N+1
    list_select_related  = ("user",)

    def get_queryset(self, request):
        return (
            super().get_queryset(request)
            .select_related("user")
            .prefetch_related("feature_bans")
        )

    fieldsets = (
        ("User Info", {
            "fields": ("user", "email_verified", "created_at"),
        }),
        ("Premium Access", {
            "fields": ("is_premium", "premium_granted_at"),
            "description": (
                "Toggle <strong>is_premium</strong> and save. "
                "Grant/revoke date is tracked automatically."
            ),
        }),
        ("Active Bans Summary", {
            "fields": ("active_bans_display",),
            "description": (
                "Read-only overview. "
                "To add, edit or delete a ban use the <strong>Active Bans</strong> "
                "inline table below, or use the <strong>bulk actions</strong> on the "
                "list view to apply bans to multiple users at once."
            ),
        }),
    )

    actions = [
        # ── Custom (shows intermediate form) ──
        "action_ban_custom",
        "action_unban_select",
        # ── Quick full-account bans ──
        "action_ban_full_1day",
        "action_ban_full_2days",
        "action_ban_full_3days",
        "action_ban_full_7days",
        "action_ban_full_permanent",
        # ── Quick mode-specific bans ──
        "action_ban_regular_3days",
        "action_ban_uncensored_permanent",
        "action_ban_ocr_3days",
        "action_ban_multi_all_3days",
        "action_ban_multi_premium_permanent",
        # ── Unban ──
        "action_unban_all",
        # ── Premium ──
        "grant_premium",
        "revoke_premium",
    ]

    # ── Prevent accidental deletion ───────────────────────────────────────────

    def get_actions(self, request):
        """Remove bulk 'Delete selected profiles' to prevent accidental mass deletion.
        Individual profiles can still be deleted from their detail page."""
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    # ── Display helpers ───────────────────────────────────────────────────────

    def username_col(self, obj):
        return obj.user.username
    username_col.short_description = "Username"
    username_col.admin_order_field = "user__username"

    def email_col(self, obj):
        return obj.user.email
    email_col.short_description = "Email"
    email_col.admin_order_field = "user__email"

    def premium_col(self, obj):
        if obj.is_premium:
            return format_html('<span style="color:#16a34a;font-weight:700;">★ Premium</span>')
        return format_html('<span style="color:#6b7280;">Free</span>')
    premium_col.short_description = "Plan"

    def ban_summary_col(self, obj):
        try:
            active = obj.get_active_bans()
        except Exception:
            return "—"
        if not active:
            return format_html('<span style="color:#16a34a;">✓ No bans</span>')
        if "full_account" in active:
            ban = active["full_account"]
            if ban.expires_at:
                d = max(0, (ban.expires_at - timezone.now()).days)
                return format_html(
                    '<span style="color:#dc2626;font-weight:700;">⛔ Full ({} day{} left)</span>',
                    d, "s" if d != 1 else "",
                )
            return format_html(
                '<span style="color:#dc2626;font-weight:700;">⛔ Full Ban (Permanent)</span>'
            )
        parts = []
        for f, ban in active.items():
            label = _feature_short_label(f)
            if ban.expires_at:
                d = max(0, (ban.expires_at - timezone.now()).days)
                parts.append(f"{label} ({d}d)")
            else:
                parts.append(f"{label} (∞)")
        return format_html(
            '<span style="color:#f59e0b;font-weight:700;">⚠ {}</span>',
            " | ".join(parts),
        )
    ban_summary_col.short_description = "Bans"

    def active_bans_display(self, obj):
        try:
            active = obj.get_active_bans()
        except Exception:
            return format_html('<span style="color:#dc2626;">Error loading bans</span>')
        if not active:
            return format_html(
                '<strong style="color:#16a34a;">No active bans — account fully operational</strong>'
            )
        # Build rows with proper escaping (ban.reason is user-controlled)
        rows = []
        for f, ban in active.items():
            label  = FEATURE_LABELS.get(f, f)
            expiry = (
                ban.expires_at.strftime("%Y-%m-%d %H:%M UTC")
                if ban.expires_at else "Permanent"
            )
            rows.append(format_html(
                "<tr>"
                '<td style="padding:4px 8px;"><b>{}</b></td>'
                '<td style="padding:4px 8px;color:#dc2626;">{}</td>'
                '<td style="padding:4px 8px;">{}</td>'
                "</tr>",
                label, expiry, ban.reason or "—",
            ))
        header = mark_safe(
            '<table style="border-collapse:collapse;width:100%;margin-top:6px;">'
            "<thead><tr>"
            '<th style="text-align:left;padding:4px 8px;background:#f5f5f5;">Feature</th>'
            '<th style="text-align:left;padding:4px 8px;background:#f5f5f5;">Expires</th>'
            '<th style="text-align:left;padding:4px 8px;background:#f5f5f5;">Reason</th>'
            "</tr></thead><tbody>"
        )
        footer = mark_safe("</tbody></table>")
        return mark_safe(str(header) + "".join(str(r) for r in rows) + str(footer))
    active_bans_display.short_description = "Current Bans"

    def save_model(self, request, obj, form, change):
        if obj.is_premium and not obj.premium_granted_at:
            obj.premium_granted_at = timezone.now()
        elif not obj.is_premium:
            obj.premium_granted_at = None
        super().save_model(request, obj, form, change)

    # ── Custom ban action (intermediate form) ─────────────────────────────────

    @admin.action(description="⛔ Custom ban — choose features, duration & reason…")
    def action_ban_custom(self, request, queryset):
        if "apply_ban" in request.POST:
            form = BanUsersForm(request.POST)
            if form.is_valid():
                features     = form.cleaned_data["features"]
                duration_val = form.cleaned_data["duration"]
                reason       = form.cleaned_data.get("reason", "")
                if duration_val == "permanent":
                    days = None
                elif duration_val == "custom":
                    days = form.cleaned_data["custom_days"]
                else:
                    days = int(duration_val)
                ids      = request.POST.getlist("_selected_action")
                profiles = Profile.objects.filter(pk__in=ids)
                try:
                    n     = _apply_bans(profiles, features, days, reason)
                    label = "permanently" if days is None else f"for {days} day(s)"
                    self.message_user(
                        request,
                        f"Banned {n} user(s) {label} from: {', '.join(features)}.",
                        messages.SUCCESS,
                    )
                except Exception as exc:
                    self.message_user(
                        request, f"Error applying bans: {exc}", messages.ERROR
                    )
                return redirect(request.get_full_path())
        else:
            form = BanUsersForm()

        return render(request, "admin/accounts/ban_action.html", {
            "form":                 form,
            "queryset":             queryset,
            "action_checkbox_name": admin.helpers.ACTION_CHECKBOX_NAME,
            "title":                "Custom Ban — Choose Features, Duration & Reason",
            "opts":                 self.model._meta,
        })

    # ── Selective unban action ────────────────────────────────────────────────

    @admin.action(description="✅ Remove specific bans — choose features to unban…")
    def action_unban_select(self, request, queryset):
        if "apply_unban" in request.POST:
            features = request.POST.getlist("features") or None
            ids      = request.POST.getlist("_selected_action")
            profiles = Profile.objects.filter(pk__in=ids)
            try:
                deleted = _remove_bans(profiles, features)
                self.message_user(
                    request,
                    f"Removed {deleted} ban(s) from {profiles.count()} user(s).",
                    messages.SUCCESS,
                )
            except Exception as exc:
                self.message_user(
                    request, f"Error removing bans: {exc}", messages.ERROR
                )
            return redirect(request.get_full_path())

        return render(request, "admin/accounts/unban_action.html", {
            "feature_choices":      FEATURE_CHOICES,
            "queryset":             queryset,
            "action_checkbox_name": admin.helpers.ACTION_CHECKBOX_NAME,
            "title":                "Remove Specific Bans",
            "opts":                 self.model._meta,
        })

    # ── Quick preset ban actions (all wrapped in try/except) ─────────────────

    def _quick_ban(self, request, queryset, features, days, reason, label):
        try:
            n = _apply_bans(queryset, features, days, reason)
            self.message_user(request, f"{label} — applied to {n} user(s).", messages.SUCCESS)
        except Exception as exc:
            self.message_user(request, f"Error: {exc}", messages.ERROR)

    @admin.action(description="⛔ Full account — 1 day")
    def action_ban_full_1day(self, request, queryset):
        self._quick_ban(request, queryset, ["full_account"], 1, "", "1-day full account ban")

    @admin.action(description="⛔ Full account — 2 days")
    def action_ban_full_2days(self, request, queryset):
        self._quick_ban(request, queryset, ["full_account"], 2, "", "2-day full account ban")

    @admin.action(description="⛔ Full account — 3 days")
    def action_ban_full_3days(self, request, queryset):
        self._quick_ban(request, queryset, ["full_account"], 3, "", "3-day full account ban")

    @admin.action(description="⛔ Full account — 7 days")
    def action_ban_full_7days(self, request, queryset):
        self._quick_ban(request, queryset, ["full_account"], 7, "", "7-day full account ban")

    @admin.action(description="⛔ Full account — Permanent")
    def action_ban_full_permanent(self, request, queryset):
        self._quick_ban(request, queryset, ["full_account"], None, "", "Permanent full account ban")

    @admin.action(description="⛔ Regular mode — 3 days")
    def action_ban_regular_3days(self, request, queryset):
        self._quick_ban(request, queryset, ["regular"], 3, "", "3-day Regular mode ban")

    @admin.action(description="⛔ Uncensored mode — Permanent")
    def action_ban_uncensored_permanent(self, request, queryset):
        self._quick_ban(
            request, queryset, ["uncensored"], None,
            "Uncensored mode access revoked.", "Permanent Uncensored mode ban",
        )

    @admin.action(description="⛔ OCR mode — 3 days")
    def action_ban_ocr_3days(self, request, queryset):
        self._quick_ban(request, queryset, ["ocr"], 3, "", "3-day OCR ban")

    @admin.action(description="⛔ Multi-Debugger (all tiers) — 3 days")
    def action_ban_multi_all_3days(self, request, queryset):
        self._quick_ban(request, queryset, ["multi_debugger"], 3, "", "3-day Multi-Debugger ban")

    @admin.action(description="⛔ Multi-Debugger Premium tier — Permanent")
    def action_ban_multi_premium_permanent(self, request, queryset):
        self._quick_ban(
            request, queryset, ["multi_debugger_premium"], None,
            "Premium tier access revoked.", "Permanent Multi-Debugger Premium ban",
        )

    @admin.action(description="✅ Remove ALL bans from selected users")
    def action_unban_all(self, request, queryset):
        try:
            deleted = _remove_bans(queryset)
            self.message_user(
                request,
                f"Removed all bans ({deleted} entries) from {queryset.count()} user(s).",
                messages.SUCCESS,
            )
        except Exception as exc:
            self.message_user(request, f"Error removing bans: {exc}", messages.ERROR)

    # ── Premium actions ───────────────────────────────────────────────────────

    @admin.action(description="✅ Grant premium access")
    def grant_premium(self, request, queryset):
        try:
            updated = queryset.filter(is_premium=False).update(
                is_premium=True, premium_granted_at=timezone.now()
            )
            self.message_user(
                request,
                f"Granted premium to {updated} user(s).",
                messages.SUCCESS,
            )
        except Exception as exc:
            self.message_user(request, f"Error granting premium: {exc}", messages.ERROR)

    @admin.action(description="🚫 Revoke premium access")
    def revoke_premium(self, request, queryset):
        try:
            updated = queryset.filter(is_premium=True).update(
                is_premium=False, premium_granted_at=None
            )
            self.message_user(
                request,
                f"Revoked premium from {updated} user(s).",
                messages.SUCCESS,
            )
        except Exception as exc:
            self.message_user(request, f"Error revoking premium: {exc}", messages.ERROR)
