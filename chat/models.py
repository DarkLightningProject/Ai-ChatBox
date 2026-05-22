from django.db import models
from django.conf import settings

class ChatSession(models.Model):
    MODE_CHOICES = (
        ('regular', 'Regular'),
        ('uncensored', 'Uncensored'),
        ('ocr', 'OCR'),
        ('multi_debugger', 'Multi-Debugger'),
    )
    session_id = models.CharField(max_length=64, unique=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="chat_sessions"
    )
    title = models.CharField(max_length=200, blank=True, null=True)
    mode = models.CharField(max_length=16, choices=MODE_CHOICES, default='regular')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.session_id} [{self.mode}]"


class Message(models.Model):
    ROLE_CHOICES = (
        ('system', 'System'),
        ('user', 'User'),
        ('assistant', 'Assistant'),
    )
    # ForeignKey stored in the same 'session_id' column — all existing
    # filter(session_id=...) / create(session_id=...) queries keep working
    # because Django names the attname 'session_id' (the FK field name)
    # when to_field points to a non-PK unique field.
    session = models.ForeignKey(
        ChatSession,
        to_field='session_id',
        db_column='session_id',
        on_delete=models.CASCADE,
        related_name='messages',
    )
    mode = models.CharField(max_length=16, default='regular')
    role = models.CharField(max_length=16, choices=ROLE_CHOICES)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    attachments = models.JSONField(default=list, blank=True)
    agent_data = models.JSONField(null=True, blank=True, default=None)

    class Meta:
        ordering = ["timestamp"]

    def __str__(self):
        return f"{self.timestamp:%Y-%m-%d %H:%M} {self.session_id} {self.role}"


class ModelUsage(models.Model):
    """Tracks token usage per LLM API call, scoped to a user."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='model_usages',
    )
    model_name = models.CharField(max_length=120, db_index=True)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['user', 'model_name'], name='chat_modelusage_user_model_idx')]

    def __str__(self):
        return f"{self.user_id} | {self.model_name} | in={self.input_tokens} out={self.output_tokens}"
