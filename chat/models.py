from django.db import models

class ChatSession(models.Model):
    MODE_CHOICES = (
        ('regular', 'Regular'),
        ('uncensored', 'Uncensored'),
        ('ocr', 'OCR'),
    )
    session_id = models.CharField(max_length=64, unique=True, db_index=True)
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
    # keeping a simple string session_id to match your existing queries
    session_id = models.CharField(max_length=64, db_index=True)
    mode = models.CharField(max_length=16, default='regular')
    role = models.CharField(max_length=16, choices=ROLE_CHOICES)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    attachments = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["timestamp"]

    def __str__(self):
        return f"{self.timestamp:%Y-%m-%d %H:%M} {self.session_id} {self.role}"
