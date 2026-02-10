from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, get_user_model
from django.contrib import messages
from django.db import models
from .models import Conversation, Message, ChatRequest, Profile
from .forms import ProfileForm

def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('conversation_list')
    else:
        form = UserCreationForm()
    return render(request, 'registration/register.html', {'form': form})

import qrcode
from django.http import HttpResponse
from io import BytesIO

@never_cache
@login_required
def my_qr(request):
    url = request.build_absolute_uri(
        f"/chat/send-request/?username={request.user.username}"
    )
    qr = qrcode.make(url)
    buffer = BytesIO()
    qr.save(buffer, format="PNG")
    return HttpResponse(buffer.getvalue(), content_type="image/png")

@never_cache
@login_required
def profile(request):
    Profile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=request.user.profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated.")
            return redirect('conversation_list')
    else:
        form = ProfileForm(instance=request.user.profile)
    return render(request, 'chat/profile.html', {'form': form})

@never_cache
@login_required
def sent_requests(request):
    sent = ChatRequest.objects.filter(sender=request.user)
    return render(request, 'chat/sent_requests.html', {'requests': sent})

@never_cache
@login_required
def conversation_list(request):
    conversations = Conversation.objects.filter(participants=request.user)
    return render(request, 'chat/conversation_list.html', {
        'conversations': conversations
    })

from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string

@never_cache
@login_required
def conversation_detail(request, pk):
    conversation = get_object_or_404(
        Conversation,
        pk=pk,
        participants=request.user
    )

    if request.method == 'POST':
        content = request.POST.get('content')
        file = request.FILES.get('file')
        is_audio = request.POST.get('is_audio') == 'true'
        parent_id = request.POST.get('parent_id')

        if content or file:
            parent = None
            if parent_id:
                parent = get_object_or_404(Message, id=parent_id)

            msg = Message.objects.create(
                conversation=conversation,
                sender=request.user,
                content=content,
                file=file,
                is_audio=is_audio,
                parent=parent
            )
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'success',
                    'message_id': msg.id,
                    'timestamp': msg.timestamp.strftime('%H:%M')
                })
        return redirect('conversation_detail', pk=pk)

    msgs = conversation.messages.order_by('timestamp')
    other_user = conversation.get_other_user(request.user)

    return render(request, 'chat/conversation_detail.html', {
        'conversation': conversation,
        'chat_messages': msgs,
        'other_user': other_user
    })

@never_cache
@login_required
def get_messages(request, pk):
    """API for AJAX message polling"""
    conversation = get_object_or_404(Conversation, pk=pk, participants=request.user)
    after_id = request.GET.get('after', 0)
    
    try:
        after_id = int(after_id)
    except (ValueError, TypeError):
        after_id = 0
        
    # We fetch ALL messages modified after a certain point or just the last 50 for status sync
    # For simplicity and to catch deletions of OLD messages, let's just return the last 50 messages
    # and let the frontend decide what to add or update.
    msgs = conversation.messages.order_by('-timestamp')[:50]
    msgs = reversed(msgs) # Back to chronological
        
    data = []
    for m in msgs:
        # If user deleted for themselves, skip
        if request.user in m.deleted_by.all():
            continue
            
        data.append({
            'id': m.id,
            'sender': m.sender.username,
            'content': m.decrypted_content if not m.is_deleted else None,
            'timestamp': m.timestamp.strftime('%H:%M'),
            'is_me': m.sender == request.user,
            'is_deleted': m.is_deleted,
            'file_url': m.file.url if m.file and not m.is_deleted else None,
            'is_image': m.is_image,
            'is_audio': m.is_audio,
            'parent_id': m.parent.id if m.parent and not m.parent.is_deleted else None,
            'parent_sender': m.parent.sender.username if m.parent and not m.parent.is_deleted else None,
            'parent_content': (m.parent.decrypted_content or m.parent.content) if m.parent and not m.parent.is_deleted else None,
        })
    
    return JsonResponse(data, safe=False)

@never_cache
@login_required
def inbox(request):
    received_requests = ChatRequest.objects.filter(receiver=request.user, accepted=False)
    return render(request, 'chat/inbox.html', {'requests': received_requests})

@never_cache
@login_required
def accept_request(request, request_id):
    chat_request = get_object_or_404(ChatRequest, id=request_id, receiver=request.user)
    chat_request.accepted = True
    chat_request.save()

    # Check if a conversation between these two already exists
    conversation = Conversation.objects.filter(participants=chat_request.sender).filter(participants=chat_request.receiver).first()
    
    if not conversation:
        conversation = Conversation.objects.create()
        conversation.participants.add(chat_request.sender, chat_request.receiver)

    messages.success(request, f"Accepted request from {chat_request.sender.username}")
    return redirect('conversation_detail', pk=conversation.pk)

@never_cache
@login_required
def send_request(request):
    if request.method == 'POST':
        username = request.POST.get('username')

        if not username:
            messages.error(request, "Username is required.")
            return redirect('conversation_list')

        try:
            receiver = get_user_model().objects.get(username=username)

            if receiver == request.user:
                # Automatic acceptance for self-chat
                chat_request, created = ChatRequest.objects.get_or_create(
                    sender=request.user,
                    receiver=request.user,
                    accepted=True
                )
                conversation = Conversation.objects.filter(participants=request.user).annotate(num_p=models.Count('participants')).filter(num_p=1).first()
                if not conversation:
                    conversation = Conversation.objects.create()
                    conversation.participants.add(request.user)
                return redirect('conversation_detail', pk=conversation.pk)
            else:
                ChatRequest.objects.get_or_create(
                    sender=request.user,
                    receiver=receiver
                )
                messages.success(request, "Chat request sent.")

        except get_user_model().DoesNotExist:
            messages.error(request, f"User {username} not found.")

    return redirect('conversation_list')
    

@never_cache
@login_required
def delete_message(request, message_id):
    """Handle message deletion - both 'for me' and 'for everyone'"""
    message = get_object_or_404(Message, id=message_id)
    conversation = message.conversation
    
    # Check if user is part of the conversation
    if request.user not in conversation.participants.all():
        messages.error(request, "You don't have permission to delete this message.")
        return redirect('conversation_list')
    
    delete_type = request.POST.get('delete_type', 'for_me')
    
    if delete_type == 'for_everyone':
        # Only sender can delete for everyone
        if message.sender == request.user:
            message.is_deleted = True
            message.save()
            messages.success(request, "Message deleted for everyone.")
        else:
            messages.error(request, "You can only delete your own messages for everyone.")
    else:  # delete_type == 'for_me'
        message.deleted_by.add(request.user)
        messages.success(request, "Message deleted for you.")
    
    return redirect('conversation_detail', pk=conversation.pk)


@never_cache
@login_required
def add_reaction(request, message_id):
    """Add emoji reaction to a message"""
    from .models import MessageReaction
    
    message = get_object_or_404(Message, id=message_id)
    conversation = message.conversation
    
    # Check if user is part of the conversation
    if request.user not in conversation.participants.all():
        messages.error(request, "You don't have permission to react to this message.")
        return redirect('conversation_list')
    
    emoji = request.POST.get('emoji', '👍')
    
    # Toggle reaction - if exists, remove it; if not, add it
    reaction, created = MessageReaction.objects.get_or_create(
        message=message,
        user=request.user,
        emoji=emoji
    )
    
    if not created:
        reaction.delete()
        messages.success(request, "Reaction removed.")
    else:
        messages.success(request, "Reaction added.")
    
    return redirect('conversation_detail', pk=conversation.pk)
