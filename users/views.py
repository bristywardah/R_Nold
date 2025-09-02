from rest_framework import generics, permissions, status, filters, viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.parsers import MultiPartParser, FormParser
import random, string
from users.enums import UserRole
from users.serializers import (
    UserSignupSerializer,
    UserProfileUpdateSerializer,
    UserSerializer,
    UserLoginResponseSerializer,
    SellerApplicationSerializer,
    VendorListSerializer,
    CustomerListSerializer,
    CustomerDetailSerializer,
    UserLoginSerializer,
    OTPSerializer,
    VerifyOTPSerializer,
    ChangePasswordSerializer,
    SetNewPasswordSerializer, 
    BulkUserActionSerializer,
    BulkSellerAppActionSerializer,
)
from users.models import User, SellerApplication
from users.enums import SellerApplicationStatus
from .firebase_auth import authenticate_firebase_user
from drf_yasg.utils import swagger_auto_schema
from rest_framework.permissions import AllowAny
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.core.mail import send_mail
from datetime import timedelta
from django.conf import settings






# ----------------------
# Profile Retrieval
# ----------------------
class UserProfileView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


# ----------------------
# User List for Admin
# ----------------------
class UserListView(viewsets.ModelViewSet):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = User.objects.all()
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['email', 'first_name', 'last_name']
    ordering_fields = ['email', 'first_name', 'last_name', 'role']

    def get_queryset(self):
        queryset = super().get_queryset()
        role = self.request.query_params.get('role')
        if role in ['vendor', 'customer', 'admin']:
            queryset = queryset.filter(role=role)
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page if page else queryset, many=True)
        return self.get_paginated_response({
            "total_users": queryset.count(),
            "users": serializer.data
        }) if page else Response({
            "total_users": queryset.count(),
            "users": serializer.data
        })






class UnifiedLoginView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    
    # Add a dummy serializer to satisfy DRF/Swagger
    serializer_class = UserLoginSerializer  

    @swagger_auto_schema(
        request_body=UserLoginSerializer,
        responses={200: UserLoginResponseSerializer}
    )
    def post(self, request, *args, **kwargs):
        id_token = request.data.get("id_token")
        if id_token:
            user = authenticate_firebase_user(id_token)
            if not user:
                return Response({"detail": "Invalid Firebase token."}, status=status.HTTP_401_UNAUTHORIZED)
        else:
            # Local email/password login
            serializer = UserLoginSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user = authenticate(
                request,
                email=serializer.validated_data['email'],
                password=serializer.validated_data['password']
            )
            if not user:
                return Response({"detail": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)

        # Check if user is active
        if not user.is_active:
            return Response({"detail": "User account is disabled."}, status=status.HTTP_403_FORBIDDEN)

        refresh = RefreshToken.for_user(user)

        response_data = {
            "user": user,  
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
        }

        return Response(UserLoginResponseSerializer(response_data).data)




# ----------------------
# Signup (Customer Default)
# ----------------------
class CustomerSignupView(generics.CreateAPIView):
    serializer_class = UserSignupSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        signup_serializer = self.get_serializer(data=request.data)
        signup_serializer.is_valid(raise_exception=True)
        user = signup_serializer.save(role="customer")
        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserSerializer(user).data,
            'access_token': str(refresh.access_token),
            'refresh_token': str(refresh),
        }, status=status.HTTP_201_CREATED)


# # ----------------------
# # Seller Application Create
# # ----------------------
class SellerApplicationView(generics.CreateAPIView):
    serializer_class = SellerApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]  
    parser_classes = [MultiPartParser, FormParser]

    def create(self, request, *args, **kwargs):
        if request.user.role == "vendor":
            return Response({"detail": "You are already a seller."}, status=status.HTTP_400_BAD_REQUEST)

        if SellerApplication.objects.filter(user=request.user, status=SellerApplicationStatus.PENDING.value).exists():
            return Response({"detail": "You already have a pending application."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)




# ----------------------
# Seller Application Management (Admin)
# ----------------------
class SellerApplicationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SellerApplication.objects.all()
    serializer_class = SellerApplicationSerializer
    permission_classes = [permissions.IsAdminUser] 


    @action(detail=False, methods=['post'], url_path='bulk-update-status', permission_classes=[permissions.IsAdminUser])
    def bulk_update_status(self, request):
        serializer = BulkSellerAppActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        app_ids = serializer.validated_data['application_ids']
        new_status = serializer.validated_data['status']
        updated = SellerApplication.objects.filter(id__in=app_ids).update(status=new_status)
        return Response({'updated_count': updated, 'new_status': new_status}, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        application = self.get_object()

        if application.status == SellerApplicationStatus.APPROVED.value:
            return Response({"detail": "Application already approved."}, status=status.HTTP_400_BAD_REQUEST)

        application.status = SellerApplicationStatus.APPROVED.value
        application.verification_code = ''.join(
            random.choices(string.ascii_uppercase + string.digits, k=6)
        )
        application.user.role = "vendor"
        application.user.save()
        application.save()

        return Response({
            "detail": "Application approved successfully.",
            "verification_code": application.verification_code,
            "user_role": application.user.role
        }, status=status.HTTP_200_OK)




    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        application = self.get_object()

        if application.status != SellerApplicationStatus.PENDING.value:
            return Response({"detail": "Only pending applications can be cancelled."}, status=status.HTTP_400_BAD_REQUEST)

        application.status = SellerApplicationStatus.CANCELLED.value
        application.save()

        return Response({
            "detail": "Application cancelled successfully."
        }, status=status.HTTP_200_OK)







# ----------------------
# Profile Update
# ----------------------
class UserProfileUpdateView(generics.UpdateAPIView):
    serializer_class = UserProfileUpdateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user




class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAdminUser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['email', 'first_name', 'last_name']
    ordering_fields = ['email', 'first_name', 'last_name', 'role']
    ordering = ['email']
    lookup_field = 'id' 

    @action(detail=False, methods=['post'], url_path='bulk-delete', permission_classes=[permissions.IsAdminUser])
    def bulk_delete(self, request):
        serializer = BulkUserActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_ids = serializer.validated_data['user_ids']
        deleted, _ = User.objects.filter(id__in=user_ids).delete()
        return Response({'deleted_count': deleted}, status=status.HTTP_200_OK)




class CustomerListViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.filter(role=UserRole.CUSTOMER.value).order_by("-created_at")
    permission_classes = [permissions.IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["first_name", "last_name", "email"]
    filterset_fields = ["role"]
    ordering_fields = ["created_at", "last_login"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return CustomerDetailSerializer
        return CustomerListSerializer




class VendorListViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.filter(role=UserRole.VENDOR.value).order_by("-created_at")
    serializer_class = VendorListSerializer
    permission_classes = [permissions.IsAdminUser]

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    ordering_fields = ['email', 'first_name', 'last_name', 'role',"created_at"]
    filterset_fields = ["role"]







class SendPasswordResetOTPView(GenericAPIView):
    serializer_class = OTPSerializer
    permission_classes = [AllowAny]
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        try:
            user = User.objects.get(email=email)
            # if not user.is_verified:
            #     return Response({'error': 'User is not verified. Cannot send reset OTP.'}, status=400)
            now = timezone.now()
            if not user.otp_request_reset_time or now > user.otp_request_reset_time + timedelta(hours=1):
                user.otp_request_count = 0
                user.otp_request_reset_time = now
            if user.otp_request_count >= 5:
                return Response({'error': 'Too many OTP requests.', 'detail': 'Try again after 1 hour.'},
                                status=status.HTTP_429_TOO_MANY_REQUESTS)
            otp = str(random.randint(100000, 999999))
            user.otp = otp
            user.otp_created_at = now
            user.otp_request_count += 1
            user.reset_password = False  
            user.save(update_fields=['otp', 'otp_created_at', 'otp_request_count', 'otp_request_reset_time', 'reset_password'])
            send_mail(
                subject='Reset Your Password',
                message=f'Your OTP to reset your password is {otp}',
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[email],
                fail_silently=False
            )
            return Response({'message': 'Password reset OTP sent successfully', 'email': email}, status=200)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=404)




class VerifyPasswordResetOTPView(GenericAPIView):
    serializer_class = VerifyOTPSerializer
    permission_classes = [AllowAny]
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        otp = serializer.validated_data['otp']
        try:
            user = User.objects.get(email=email, otp=otp)
            # if not user.is_verified:
            #     return Response({'error': 'User is not verified'}, status=400)

            if not user.otp_created_at or timezone.now() > user.otp_created_at + timedelta(minutes=1):
                return Response({'error': 'OTP has expired'}, status=400)
            user.otp = ''
            user.otp_created_at = None
            user.reset_password = True
            user.save(update_fields=['otp', 'otp_created_at', 'reset_password'])
            return Response({'message': 'OTP verified. You can now reset your password.', 'email': email}, status=200)
        except User.DoesNotExist:
            return Response({'error': 'Invalid OTP or email'}, status=400)









class ChangePasswordView(GenericAPIView):
    serializer_class = ChangePasswordSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request}) 
        serializer.is_valid(raise_exception=True)
        old_password = serializer.validated_data['old_password']
        new_password = serializer.validated_data['new_password']
        user = request.user

        if not user.check_password(old_password):
            return Response(
                {'error': 'Old password is incorrect', 'detail': 'The old password you provided does not match your current password.'},
                status=status.HTTP_400_BAD_REQUEST
            )
 
        user.set_password(new_password)
        user.save(update_fields=["password"])
        full_name = f"{user.first_name} {user.last_name}".strip()
        return Response(
            {'message': 'Password changed successfully', 'full_name': full_name},
            status=status.HTTP_200_OK
        )




class SetNewPasswordView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = SetNewPasswordSerializer
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        new_password = serializer.validated_data['new_password']
        try:
            user = User.objects.get(email=email)

            if not user.reset_password:
                return Response(
                    {'error': 'Forbidden', 'detail': 'OTP verification required before resetting password.'},
                    status=status.HTTP_403_FORBIDDEN
                )
            user.set_password(new_password)
            user.reset_password = False
            user.save(update_fields=['password', 'reset_password'])
            return Response(
                {'message': 'Password reset successful.'},
                status=status.HTTP_200_OK
            )
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found', 'detail': 'No user registered with this email address.'},
                status=status.HTTP_404_NOT_FOUND
            )
        





