from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Profile, Conversation, Message, ChatRequest, MessageReaction

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model"""
    profile_image = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'date_joined', 'profile_image']
        read_only_fields = ['id', 'date_joined']

    def get_profile_image(self, obj):
        try:
            if obj.profile and obj.profile.image:
                return obj.profile.image.url
        except:
            pass
        return None


class ProfileSerializer(serializers.ModelSerializer):
    """Serializer for Profile model"""
    username = serializers.CharField(source='user.username', read_only=True)
    first_name = serializers.CharField(source='user.first_name', required=False)
    last_name = serializers.CharField(source='user.last_name', required=False)
    
    class Meta:
        model = Profile
        fields = ['id', 'user', 'username', 'first_name', 'last_name', 'image']
        read_only_fields = ['id', 'user']

    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', {})
        first_name = user_data.get('first_name')
        last_name = user_data.get('last_name')
        
        if first_name is not None:
            instance.user.first_name = first_name
        if last_name is not None:
            instance.user.last_name = last_name
        
        instance.user.save()
        return super().update(instance, validated_data)


class MessageReactionSerializer(serializers.ModelSerializer):
    """Serializer for MessageReaction model"""
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = MessageReaction
        fields = ['id', 'message', 'user', 'emoji', 'created_at']
        read_only_fields = ['id', 'created_at']


class MessageSerializer(serializers.ModelSerializer):
    """Serializer for Message model"""
    sender = UserSerializer(read_only=True)
    reactions = MessageReactionSerializer(many=True, read_only=True)
    decrypted_content = serializers.CharField(read_only=True)
    is_image = serializers.BooleanField(read_only=True)
    parent_content = serializers.SerializerMethodField()
    
    class Meta:
        model = Message
        fields = [
            'id', 'conversation', 'sender', 'content', 'decrypted_content',
            'file', 'is_audio', 'is_image', 'parent', 'timestamp', 'is_deleted',
            'deleted_by', 'reactions', 'parent_content'
        ]
        read_only_fields = ['id', 'sender', 'timestamp', 'decrypted_content', 'is_image']

    def get_parent_content(self, obj):
        if obj.parent:
            return obj.parent.decrypted_content
        return None


class ConversationSerializer(serializers.ModelSerializer):
    """Serializer for Conversation model"""
    participants = UserSerializer(many=True, read_only=True)
    last_message = serializers.SerializerMethodField()
    other_user = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Conversation
        fields = ['id', 'participants', 'created_at', 'last_message', 'other_user', 'unread_count']
        read_only_fields = ['id', 'created_at']
    
    def get_last_message(self, obj):
        request = self.context.get('request')
        user = request.user if request else None
        if user:
            last_msg = obj.get_last_visible_message(user)
            if last_msg:
                return MessageSerializer(last_msg).data
        return None
    
    def get_other_user(self, obj):
        request = self.context.get('request')
        if request and request.user:
            other = obj.participants.exclude(id=request.user.id).first()
            if other:
                return UserSerializer(other).data
        return None
    
    def get_unread_count(self, obj):
        request = self.context.get('request')
        user = request.user if request else None
        if user:
            return obj.messages.exclude(sender=user).exclude(read_by=user).count()
        return 0


class ChatRequestSerializer(serializers.ModelSerializer):
    """Serializer for ChatRequest model"""
    sender = UserSerializer(read_only=True)
    receiver = UserSerializer(read_only=True)
    receiver_username = serializers.CharField(write_only=True, required=False)
    
    class Meta:
        model = ChatRequest
        fields = ['id', 'sender', 'receiver', 'receiver_username', 'created_at', 'accepted']
        read_only_fields = ['id', 'sender', 'created_at', 'accepted']
    
    def create(self, validated_data):
        receiver_username = validated_data.pop('receiver_username', None)
        if receiver_username:
            try:
                receiver = User.objects.get(username=receiver_username)
                validated_data['receiver'] = receiver
            except User.DoesNotExist:
                raise serializers.ValidationError({'receiver_username': 'User not found'})
        
        return super().create(validated_data)
