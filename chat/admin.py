from django.contrib import admin
from .models import ChatSession, Message


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = (
        "session_id",
        "mode",
        "title",
        "created_at",
        "updated_at",
    )
    list_filter = ("mode", "created_at")
    search_fields = ("session_id", "title")
    ordering = ("-updated_at",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = (
        "session_id",
        "role",
        "mode",
        "short_content",
        "timestamp",
    )
    list_filter = ("role", "mode", "timestamp")
    search_fields = ("session_id", "content")
    ordering = ("-timestamp",)
    readonly_fields = ("timestamp",)

    def short_content(self, obj):
        return obj.content[:60] + ("…" if len(obj.content) > 60 else "")

    short_content.short_description = "Content"
