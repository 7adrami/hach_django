from rest_framework import viewsets, status, permissions, serializers
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model, authenticate
from django.shortcuts import get_object_or_404
from .models import Conversation, Message, ChatRequest, Profile, MessageReaction
from .serializers import (
    UserSerializer, ConversationSerializer, MessageSerializer,
    ChatRequestSerializer, ProfileSerializer, MessageReactionSerializer
)

User = get_user_model()


# Authentication Views
@api_view(['POST'])
@permission_classes([AllowAny])
def register_api(request):
    """Register a new user and return JWT tokens"""
    username = request.data.get('username')
    password = request.data.get('password')
    email = request.data.get('email', '')
    
    if not username or not password:
        return Response({'error': 'Username and password required'}, status=status.HTTP_400_BAD_REQUEST)
    
    if User.objects.filter(username=username).exists():
        return Response({'error': 'Username already exists'}, status=status.HTTP_400_BAD_REQUEST)
    
    user = User.objects.create_user(username=username, password=password, email=email)
    refresh = RefreshToken.for_user(user)
    
    return Response({
        'user': UserSerializer(user).data,
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_api(request):
    """Login and return JWT tokens"""
    username = request.data.get('username')
    password = request.data.get('password')
    
    user = authenticate(username=username, password=password)
    if user:
        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserSerializer(user).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        })
    
    return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def current_user_api(request):
    """Get current user info"""
    return Response(UserSerializer(request.user).data)


# Conversation ViewSet
class ConversationViewSet(viewsets.ModelViewSet):
    """API endpoints for conversations"""
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        print(f"DEBUG: Fetching conversations for user: {self.request.user}")
        queryset = Conversation.objects.filter(participants=self.request.user)
        print(f"DEBUG: Found {queryset.count()} conversations")
        return queryset
    
    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        """Get messages for a conversation"""
        conversation = self.get_object()
        
        # To support real-time deletions and reactions for existing messages,
        # we return the latest 50 messages. The client handles deduplication.
        queryset = conversation.messages.order_by('-timestamp')[:50]
        
        # We want the messages in chronological order for the client to process
        # (Though usually chat views show reverse, we'll keep the order consistent)
        messages = sorted(list(queryset), key=lambda x: x.timestamp)
        
        # Filter logic: if deleted for everyone, show for everyone (serializer handles content)
        # If deleted for me personally, skip.
        messages = [
            msg for msg in messages
            if request.user not in msg.deleted_by.all()
        ]
        
        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def mark_as_read(self, request, pk=None):
        """Mark all messages in a conversation as read by the current user"""
        conversation = self.get_object()
        unread_messages = conversation.messages.exclude(sender=request.user).exclude(read_by=request.user)
        for msg in unread_messages:
            msg.read_by.add(request.user)
        return Response({'status': 'Conversation marked as read'})


# Message ViewSet
class MessageViewSet(viewsets.ModelViewSet):
    """API endpoints for messages"""
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Message.objects.filter(conversation__participants=self.request.user)
    
    def perform_create(self, serializer):
        parent = serializer.validated_data.get('parent')
        if parent and parent.is_deleted:
             raise serializers.ValidationError("Cannot reply to a deleted message")
        serializer.save(sender=self.request.user)
    
    @action(detail=True, methods=['post'])
    def delete_message(self, request, pk=None):
        """Delete a message (for me or for everyone)"""
        message = self.get_object()
        delete_type = request.data.get('delete_type', 'for_me')
        
        if delete_type == 'for_everyone':
            if message.sender == request.user:
                message.is_deleted = True
                message.save()
                return Response({'status': 'Message deleted for everyone'})
            return Response({'error': 'Only sender can delete for everyone'}, status=status.HTTP_403_FORBIDDEN)
        else:
            message.deleted_by.add(request.user)
            return Response({'status': 'Message deleted for you'})
    
    @action(detail=True, methods=['post'])
    def react(self, request, pk=None):
        """Add or remove a reaction"""
        message = self.get_object()
        emoji = request.data.get('emoji', '👍')
        
        reaction, created = MessageReaction.objects.get_or_create(
            message=message,
            user=request.user,
            emoji=emoji
        )
        
        if not created:
            reaction.delete()
            return Response({'status': 'Reaction removed'})
        
        return Response({'status': 'Reaction added', 'reaction': MessageReactionSerializer(reaction).data})


# ChatRequest ViewSet
class ChatRequestViewSet(viewsets.ModelViewSet):
    """API endpoints for chat requests"""
    serializer_class = ChatRequestSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return ChatRequest.objects.filter(receiver=self.request.user, accepted=False)
    
    def perform_create(self, serializer):
        serializer.save(sender=self.request.user)
    
    @action(detail=False, methods=['get'])
    def sent(self, request):
        """Get sent requests"""
        sent_requests = ChatRequest.objects.filter(sender=request.user)
        serializer = self.get_serializer(sent_requests, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        """Accept a chat request"""
        chat_request = self.get_object()
        chat_request.accepted = True
        chat_request.save()
        
        # Create or get conversation
        conversation = Conversation.objects.filter(
            participants=chat_request.sender
        ).filter(
            participants=chat_request.receiver
        ).first()
        
        if not conversation:
            conversation = Conversation.objects.create()
            conversation.participants.add(chat_request.sender, chat_request.receiver)
        
        return Response({
            'status': 'Request accepted',
            'conversation': ConversationSerializer(conversation, context={'request': request}).data
        })


# Profile ViewSet
class ProfileViewSet(viewsets.ModelViewSet):
    """API endpoints for user profiles"""
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Profile.objects.filter(user=self.request.user)
    
    @action(detail=False, methods=['get', 'put'])
    def me(self, request):
        """Get or update current user's profile"""
        profile, created = Profile.objects.get_or_create(user=request.user)
        
        if request.method == 'PUT':
            serializer = self.get_serializer(profile, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
        
        return Response(self.get_serializer(profile).data)
