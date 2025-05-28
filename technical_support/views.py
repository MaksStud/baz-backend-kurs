import os

from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect
from django.utils.decorators import method_decorator

from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.viewsets import mixins
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.request import Request

from .serializers import TechnicalSupportChatMessageSerializer, TechnicalSupportChatSerializer
from .models import TechnicalSupportChat, TechnicalSupportChatMessage
from .utils import  send_message_via_websocket

from permission.permissions import IsRegisteredUser


class TechnicalSupportChatViewSet(viewsets.GenericViewSet,
                                   mixins.ListModelMixin,
                                   mixins.RetrieveModelMixin):
    queryset = TechnicalSupportChat.objects.all()
    serializer_class = TechnicalSupportChatSerializer
    permission_classes = [IsRegisteredUser, IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(bazhay_user=self.request.user)

    def list(self, request, *args, **kwargs):
        """
        Return list of TechnicalSupportChat objects with messages and create chat if user doesn't have one.
        """
        chat, _ = TechnicalSupportChat.objects.get_or_create(bazhay_user=request.user)
        return super().list(request, *args, **kwargs)


@method_decorator(csrf_protect, name='dispatch')
class TechnicalSupportChatView(APIView):
    """View for handling technical support chat."""

    def get(self, request: Request, pk=None):
        """Render page or get data."""
        chat = get_object_or_404(TechnicalSupportChat, pk=pk)

        if request.query_params.get('messages') == 'true':
            return self.messages(pk)
        return render(request, 'admin/technical_support_chat.html',
                      {'chat': chat, "theme": chat.title, 'server_url': os.getenv('SERVER_DOMAIN', 'localhost:8000')})

    def messages(self, pk: int) -> Response:
        """
        Return chat message.
        :param pk: Chat id.
        """
        chat = get_object_or_404(TechnicalSupportChat, pk=pk)
        messages = chat.chat_message.all().order_by('created_at')
        serializer = TechnicalSupportChatMessageSerializer(messages, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request: Request, pk: int = None) -> Response:
        """
        Send a message to the chat.
        :param request: Request.
        :param pk: Chat id.
        """
        chat: TechnicalSupportChat = get_object_or_404(TechnicalSupportChat, pk=pk)
        message_text = request.data.get("message_text")
        if message_text:
            message = TechnicalSupportChatMessage.objects.create(
                chat=chat,
                message_text=message_text,
            )
            send_message_via_websocket(chat.id, message)
            return Response({"status": "Message sent", "message_id": message.id})
        return Response({"error": "Message text is required"}, status=status.HTTP_400_BAD_REQUEST)
