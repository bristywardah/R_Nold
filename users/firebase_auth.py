import firebase_admin
from firebase_admin import credentials, auth
from users.models import User

cred = credentials.Certificate("/home/didarahmed/R_lond/firebase_service_account.json")
firebase_admin.initialize_app(cred)

def authenticate_firebase_user(id_token):
    try:
        decoded_token = auth.verify_id_token(id_token)
        uid = decoded_token["uid"]
        email = decoded_token.get("email")
        name = decoded_token.get("name")
        picture = decoded_token.get("picture")

        user, created = User.objects.get_or_create(email=email, defaults={
            "first_name": name.split(" ")[0] if name else "",
            "last_name": " ".join(name.split(" ")[1:]) if name else "",
            "profile_image": picture,
        })
        return user
    except Exception as e:
        print("Firebase token error:", e)  
        return None