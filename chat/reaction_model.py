from django.conf import settings
from django.db import models

User = settings.AUTH_USER_MODEL


class MessageReaction(models.Model):
    """Stores emoji reactions to messages"""
    message = models.ForeignKey(
        'Message',
        on_delete=models.CASCADE,
        related_name='reactions'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )
    emoji = models.CharField(max_length=10)  # Stores emoji character
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('message', 'user', 'emoji')

    def __str__(self):
        return f"{self.user.username} reacted {self.emoji} to message {self.message.id}"
