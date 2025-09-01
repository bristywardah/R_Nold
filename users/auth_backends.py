# users/auth_backends.py
from rest_framework.authentication import BaseAuthentication
from rest_framework import exceptions
from .firebase_auth import authenticate_firebase_user

class FirebaseAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return None  # No token provided

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise exceptions.AuthenticationFailed("Invalid Authorization header")

        id_token = parts[1]
        user = authenticate_firebase_user(id_token)
        if not user:
            raise exceptions.AuthenticationFailed("Invalid Firebase token")
        
        return (user, None)  # DRF expects (user, auth) tuple
