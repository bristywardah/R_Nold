from firebase_admin import auth
from users.models import User

def authenticate_firebase_user(id_token):
    try:
        decoded_token = auth.verify_id_token(id_token)
        uid = decoded_token["uid"]
        email = decoded_token.get("email")
        name = decoded_token.get("name")
        picture = decoded_token.get("picture")

        # find or create Django user
        user, created = User.objects.get_or_create(email=email, defaults={
            "first_name": name.split(" ")[0] if name else "",
            "last_name": " ".join(name.split(" ")[1:]) if name else "",
            "profile_image": picture,
        })
        return user
    except Exception as e:
        return None
