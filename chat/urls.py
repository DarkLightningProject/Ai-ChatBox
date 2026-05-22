from django.urls import path
from .views import (
    ChatView, ChatHistoryView, OcrUploadView, OcrQaView,
    create_session, list_sessions, delete_session,
    GeminiWithImagesView, rename_session, MultiDebugView, usage_stats, model_info,
)

urlpatterns = [
    path('chat/', ChatView.as_view(), name='chat'),
    path('multi-debug/', MultiDebugView.as_view(), name='multi-debug'),
    path('history/', ChatHistoryView.as_view(), name='history'),
    path('ocr/', OcrUploadView.as_view(), name='ocr'),
    path('ocr-qa/', OcrQaView.as_view(), name='ocr-qa'),

    path('create-session/', create_session, name='create-session'),

    path('sessions/', list_sessions, name='list-sessions'),
    # IMPORTANT: static route goes BEFORE the dynamic route
    path('sessions/new/', create_session, name='create-session-legacy'),
    path('sessions/<str:session_id>/delete/', delete_session, name='delete-session'),
     path("gemini-with-images/", GeminiWithImagesView.as_view(), name="gemini-with-images"),
     path("sessions/<str:session_id>/rename/", rename_session, name="rename_session"),
     path("usage/", usage_stats, name="usage-stats"),
     path("models/", model_info, name="model-info"),
]
