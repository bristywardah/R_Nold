from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken, TokenError

User = get_user_model()


@database_sync_to_async
def _get_user(user_id):
    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        return AnonymousUser()


class WebSocketJWTAuthMiddleware:

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        raw_qs = scope.get("query_string", b"")
        try:
            qs = parse_qs(raw_qs.decode())
        except Exception:
            qs = {}

        token_list = qs.get("token") or qs.get(b"token") or []
        token = token_list[0] if token_list else None

        if token:
            try:
                access_token = AccessToken(token)
                user_id = access_token.get("user_id") or access_token.get("user_id")
                if user_id:
                    scope["user"] = await _get_user(user_id)
                else:
                    scope["user"] = AnonymousUser()
            except TokenError:
                scope["user"] = AnonymousUser()
            except Exception:
                scope["user"] = AnonymousUser()
        else:
            scope["user"] = AnonymousUser()

        return await self.app(scope, receive, send)
