from rest_framework import viewsets
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAdminUser, AllowAny
from .models import Terms
from .serializers import TermsSerializer


# ✅ Admin: Full access to create, update, delete terms and privacy
class AdminTermsViewSet(viewsets.ModelViewSet):
    queryset = Terms.objects.all()
    serializer_class = TermsSerializer
    permission_classes = [IsAdminUser]


# ✅ Public: Read-Only - Latest Terms & Conditions
class TermsConditionView(RetrieveAPIView):
    serializer_class = TermsSerializer
    permission_classes = [AllowAny]

    def get_object(self):
        return Terms.objects.filter(type='terms').order_by('-created_at').first()


# ✅ Public: Read-Only - Latest Privacy Policy
class PrivacyPolicyView(RetrieveAPIView):
    serializer_class = TermsSerializer
    permission_classes = [AllowAny]

    def get_object(self):
        return Terms.objects.filter(type='privacy').order_by('-created_at').first()
