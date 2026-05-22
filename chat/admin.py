from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html

from .models import ChatSession, Message


# ─── Shared style maps ────────────────────────────────────────────────────────

MODE_COLOUR = {
    "regular":        "#3b82f6",
    "uncensored":     "#ef4444",
    "ocr":            "#8b5cf6",
    "multi_debugger": "#f59e0b",
}
MODE_ICON = {
    "regular":        "🤖",
    "uncensored":     "🔥",
    "ocr":            "📄",
    "multi_debugger": "🔍",
}
MODE_LABEL = {
    "regular":        "Regular (API)",
    "uncensored":     "Uncensored",
    "ocr":            "OCR (Gemini)",
    "multi_debugger": "Multi-Debugger",
}


# ─── Shared column renderer ──────────────────────────────────────────────────

def _mode_col_html(mode, bold=False):
    colour = MODE_COLOUR.get(mode, "#6b7280")
    icon   = MODE_ICON.get(mode, "")
    label  = MODE_LABEL.get(mode, mode)
    weight = "font-weight:600;" if bold else ""
    return format_html(
        '<span style="color:{};{}">{} {}</span>',
        colour, weight, icon, label,
    )


# ─── Custom filters ───────────────────────────────────────────────────────────

class ChatModeFilter(admin.SimpleListFilter):
    """
    Filter by chat mode with readable labels and icons.
    Replaces the raw built-in 'mode' filter.
    """
    title          = "Chat Mode"
    parameter_name = "mode"

    def lookups(self, _request, _model_admin):
        return [
            ("regular",        "🤖 Regular (API)"),
            ("uncensored",     "🔥 Uncensored"),
            ("ocr",            "📄 OCR (Gemini)"),
            ("multi_debugger", "🔍 Multi-Debugger"),
        ]

    def queryset(self, _request, queryset):
        if self.value():
            return queryset.filter(mode=self.value())
        return queryset


class SenderFilter(admin.SimpleListFilter):
    """
    Filter messages by who sent them — user or the bot.
    Replaces the raw built-in 'role' filter.
    """
    title          = "Sent By"
    parameter_name = "role"

    def lookups(self, _request, _model_admin):
        return [
            ("user",      "👤 User messages"),
            ("assistant", "🤖 Bot responses"),
            ("system",    "⚙ System messages"),
        ]

    def queryset(self, _request, queryset):
        if self.value():
            return queryset.filter(role=self.value())
        return queryset


class HasImagesFilter(admin.SimpleListFilter):
    """Filter messages that include uploaded images or files."""
    title          = "Images / Files"
    parameter_name = "has_images"

    def lookups(self, _request, _model_admin):
        return [
            ("yes", "📎 Has images or files"),
            ("no",  "Text only (no attachments)"),
        ]

    def queryset(self, _request, queryset):
        if self.value() == "yes":
            return queryset.exclude(attachments=[]).exclude(attachments=None)
        if self.value() == "no":
            return queryset.filter(attachments=[])
        return queryset


class SessionStatusFilter(admin.SimpleListFilter):
    """Filter chat sessions by whether they have any messages."""
    title          = "Session Status"
    parameter_name = "session_status"

    def lookups(self, _request, _model_admin):
        return [
            ("active",  "💬 Has messages"),
            ("empty",   "🕳 Empty (no messages yet)"),
        ]

    def queryset(self, _request, queryset):
        if self.value() == "active":
            return queryset.annotate(_c=Count("messages")).filter(_c__gt=0)
        if self.value() == "empty":
            return queryset.annotate(_c=Count("messages")).filter(_c=0)
        return queryset


# ─── ChatSession admin ────────────────────────────────────────────────────────

@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display  = (
        "title_col", "username_col", "mode_col",
        "message_count_col", "created_at", "updated_at",
    )
    list_filter      = (ChatModeFilter, SessionStatusFilter)
    search_fields    = ("session_id", "title", "user__username", "user__email")
    ordering         = ("-updated_at",)
    readonly_fields  = ("session_id", "created_at", "updated_at")
    list_select_related = ("user",)
    list_per_page    = 30
    date_hierarchy   = "created_at"

    fieldsets = (
        ("Session Info", {
            "fields": ("session_id", "title", "mode", "user"),
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _message_count=Count("messages")
        )

    def title_col(self, obj):
        title = obj.title or "Untitled"
        return format_html(
            '<span title="{}">{}</span>',
            obj.session_id,
            title[:60] + ("…" if len(title) > 60 else ""),
        )
    title_col.short_description = "Title"
    title_col.admin_order_field = "title"

    def username_col(self, obj):
        if obj.user:
            return format_html(
                '<span style="font-weight:600;">{}</span>', obj.user.username
            )
        return format_html('<span style="color:#9ca3af;">Anonymous</span>')
    username_col.short_description = "User"
    username_col.admin_order_field = "user__username"

    def mode_col(self, obj):
        return _mode_col_html(obj.mode, bold=True)
    mode_col.short_description = "Mode"
    mode_col.admin_order_field = "mode"

    def message_count_col(self, obj):
        count  = obj._message_count
        colour = "#16a34a" if count > 0 else "#9ca3af"
        return format_html(
            '<span style="color:{};">{} msg{}</span>',
            colour, count, "s" if count != 1 else "",
        )
    message_count_col.short_description = "Messages"
    message_count_col.admin_order_field = "_message_count"


# ─── Message admin ────────────────────────────────────────────────────────────

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display  = (
        "username_col", "role_col", "mode_col",
        "content_preview", "has_images_col", "has_agents_col", "timestamp",
    )
    # Filters are ordered logically: who → which mode → special content
    list_filter   = (
        SenderFilter,    # 👤 User / 🤖 Bot / ⚙ System
        ChatModeFilter,  # 🤖 Regular / 🔥 Uncensored / 📄 OCR / 🔍 Multi-Debugger
        HasImagesFilter, # 📎 Has images / Text only
    )
    search_fields = (
        "content",
        "session__session_id",
        "session__title",
        "session__user__username",
        "session__user__email",
    )
    ordering             = ("-timestamp",)
    readonly_fields      = (
        "timestamp", "session", "role", "mode",
        "content", "attachments", "agent_data",
    )
    list_select_related  = ("session", "session__user")
    list_per_page        = 50
    date_hierarchy       = "timestamp"

    fieldsets = (
        ("Message", {
            "fields": ("session", "role", "mode", "content", "timestamp"),
        }),
        ("Attachments (images / files)", {
            "fields": ("attachments",),
            "classes": ("collapse",),
        }),
        ("Multi-Debugger Agent Data", {
            "fields": ("agent_data",),
            "classes": ("collapse",),
            "description": "Only present on Multi-Debugger bot responses.",
        }),
    )

    # Read-only — messages must not be created or edited from admin,
    # but delete is allowed so cascade deletion when removing a User works.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    # ── Columns ───────────────────────────────────────────────────────────────

    def username_col(self, obj):
        user = obj.session.user if obj.session else None
        if user:
            return format_html(
                '<span style="font-weight:600;">{}</span>', user.username
            )
        return format_html('<span style="color:#9ca3af;">—</span>')
    username_col.short_description = "User"
    username_col.admin_order_field = "session__user__username"

    def role_col(self, obj):
        styles = {
            "user":      ("#3b82f6", "👤 User"),
            "assistant": ("#16a34a", "🤖 Bot"),
            "system":    ("#6b7280", "⚙ System"),
        }
        colour, label = styles.get(obj.role, ("#6b7280", obj.role))
        return format_html(
            '<span style="color:{};font-weight:600;">{}</span>', colour, label
        )
    role_col.short_description = "Sent By"
    role_col.admin_order_field = "role"

    def mode_col(self, obj):
        return _mode_col_html(obj.mode)
    mode_col.short_description = "Mode"
    mode_col.admin_order_field = "mode"

    def content_preview(self, obj):
        text    = obj.content or ""
        preview = text[:80] + ("…" if len(text) > 80 else "")
        return format_html('<span title="{}">{}</span>', text[:300], preview)
    content_preview.short_description = "Content"

    def has_images_col(self, obj):
        if obj.attachments:
            count = len(obj.attachments) if isinstance(obj.attachments, list) else 1
            return format_html('<span style="color:#8b5cf6;">📎 {}</span>', count)
        return format_html('<span style="color:#d1d5db;">—</span>')
    has_images_col.short_description = "Images"

    def has_agents_col(self, obj):
        if obj.agent_data:
            return format_html('<span style="color:#f59e0b;">🔍 Yes</span>')
        return format_html('<span style="color:#d1d5db;">—</span>')
    has_agents_col.short_description = "Multi-Debug"
