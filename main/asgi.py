

# # project/asgi.py
# import os
# import django
# from django.core.asgi import get_asgi_application
# from channels.routing import ProtocolTypeRouter, URLRouter
# from channels.auth import AuthMiddlewareStack

# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "main.settings")
# django.setup()

# from chatapp.routing import websocket_urlpatterns
# from notification.routing import websocket_urlpatterns
# from chatapp.middlewares import WebSocketJWTAuthMiddleware

# application = ProtocolTypeRouter({
#     "http": get_asgi_application(),

#     "websocket": WebSocketJWTAuthMiddleware(
#         AuthMiddlewareStack(
#             URLRouter(
#                 websocket_urlpatterns
#             )
#         )
#     ),
# })



# project/asgi.py
import os
import django
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "main.settings")
django.setup()

from chatapp.routing import websocket_urlpatterns as chat_ws
from notification.routing import websocket_urlpatterns as notification_ws
from chatapp.middlewares import WebSocketJWTAuthMiddleware

application = ProtocolTypeRouter({
    "http": get_asgi_application(),

    "websocket": WebSocketJWTAuthMiddleware(
        AuthMiddlewareStack(
            URLRouter(
                chat_ws + notification_ws 
            )
        )
    ),
})
