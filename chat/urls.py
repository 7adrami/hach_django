from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views, api_views

# REST API Router
router = DefaultRouter()
router.register(r'conversations', api_views.ConversationViewSet, basename='api-conversation')
router.register(r'messages', api_views.MessageViewSet, basename='api-message')
router.register(r'requests', api_views.ChatRequestViewSet, basename='api-request')
router.register(r'profiles', api_views.ProfileViewSet, basename='api-profile')

urlpatterns = [
    # Web URLs
    path('', views.conversation_list, name='conversation_list'),
    path('register/', views.register, name='register'),
    path('profile/', views.profile, name='profile'),
    path('sent-requests/', views.sent_requests, name='sent_requests'),

    path('send-request/', views.send_request, name='send_request'),
    path('inbox/', views.inbox, name='inbox'),
    path('accept/<int:request_id>/', views.accept_request, name='accept_request'),

    path('<int:pk>/', views.conversation_detail, name='conversation_detail'),
    path('conversation/<int:pk>/get-messages/', views.get_messages, name='get_messages'),
    
    # Message actions
    path('message/<int:message_id>/delete/', views.delete_message, name='delete_message'),
    path('message/<int:message_id>/react/', views.add_reaction, name='add_reaction'),
    
    # API URLs
    path('api/', include(router.urls)),
    path('api/auth/register/', api_views.register_api, name='api-register'),
    path('api/auth/login/', api_views.login_api, name='api-login'),
    path('api/auth/me/', api_views.current_user_api, name='api-me'),
]
