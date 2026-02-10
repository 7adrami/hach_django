from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

def home(request):
    if request.user.is_authenticated:
        return redirect('conversation_list')
    return redirect('/accounts/login/')

from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', home),
    path('admin/', admin.site.urls),
    path('chat/', include('chat.urls')),
    path('accounts/', include('django.contrib.auth.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
