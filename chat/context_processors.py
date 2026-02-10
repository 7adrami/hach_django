from .models import Conversation

def conversations_processor(request):
    if request.user.is_authenticated:
        return {
            'all_conversations': Conversation.objects.filter(participants=request.user)
        }
    return {'all_conversations': []}
