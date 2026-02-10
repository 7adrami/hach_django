from django.conf import settings
from django.db import models
from .utils import encrypt_message, decrypt_message
from django.db.models.signals import post_save
from django.dispatch import receiver

User = settings.AUTH_USER_MODEL


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    image = models.ImageField(upload_to='profiles/', default='profiles/default.png', null=True, blank=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


class Conversation(models.Model):
    participants = models.ManyToManyField(
        User,
        related_name='conversations'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Conversation {self.id}"

    def get_other_user(self, current_user):
        return self.participants.exclude(id=current_user.id).first() or current_user

    def get_last_visible_message(self, user):
        """Returns the latest message that isn't deleted for everyone and hasn't been deleted 'for me' by the user."""
        return self.messages.filter(is_deleted=False).exclude(deleted_by=user).order_by('-timestamp').first()


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )
    content = models.TextField(blank=True, null=True)
    file = models.FileField(upload_to='messages/', null=True, blank=True)
    is_audio = models.BooleanField(default=False)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='replies')
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Deletion and Read fields
    is_deleted = models.BooleanField(default=False)  # Delete for everyone
    deleted_by = models.ManyToManyField(User, related_name='deleted_messages', blank=True)  # Delete for me
    read_by = models.ManyToManyField(User, related_name='read_messages', blank=True)

    def save(self, *args, **kwargs):
        if self.content and not self.content.startswith('gAAAA'): # Simple check to avoid double encryption
            self.content = encrypt_message(self.content)
        super().save(*args, **kwargs)

    @property
    def decrypted_content(self):
        if self.content:
            return decrypt_message(self.content)
        return ""

    @property
    def is_image(self):
        if self.file:
            return self.file.name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))
        return False

    def __str__(self):
        return f"{self.sender}: {self.decrypted_content[:50]}"


class ChatRequest(models.Model):
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sent_requests'
    )
    receiver = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='received_requests'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    accepted = models.BooleanField(default=False)

    class Meta:
        unique_together = ('sender', 'receiver')

    def __str__(self):
        return f"{self.sender} → {self.receiver}"


class MessageReaction(models.Model):
    """Stores emoji reactions to messages"""
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='reactions'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )
    emoji = models.CharField(max_length=10)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('message', 'user', 'emoji')

    def __str__(self):
        return f"{self.user.username} reacted {self.emoji} to message {self.message.id}"
