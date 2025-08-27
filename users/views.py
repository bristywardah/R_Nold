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
    ForgotPasswordRequestSerializer,
    ForgotPasswordConfirmSerializer,
    UserSerializer,
    UserLoginResponseSerializer,
    UserLoginSerializer,
    SellerApplicationSerializer,
    VendorListSerializer,
    CustomerListSerializer
)
from users.models import User, SellerApplication
from users.enums import SellerApplicationStatus
from users.permissions import IsRoleAdmin


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


# ----------------------
# Login
# ----------------------
class UserLoginView(generics.GenericAPIView):
    serializer_class = UserLoginSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authenticate(
            request,
            email=serializer.validated_data['email'],
            password=serializer.validated_data['password']
        )

        if not user:
            return Response({"detail": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)
        if not user.is_active:
            return Response({"detail": "User account is disabled."}, status=status.HTTP_403_FORBIDDEN)

        refresh = RefreshToken.for_user(user)
        return Response(UserLoginResponseSerializer({
            'user': UserSerializer(user).data,
            'access_token': str(refresh.access_token),
            'refresh_token': str(refresh),
        }).data)


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


# ----------------------
# Seller Application Create
# ----------------------
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


# ----------------------
# Forgot Password
# ----------------------
class ForgotPasswordRequestView(generics.GenericAPIView):
    serializer_class = ForgotPasswordRequestSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"message": "OTP sent to your email."})


class ForgotPasswordConfirmView(generics.GenericAPIView):
    serializer_class = ForgotPasswordConfirmSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"message": "Password reset successful."})


# ----------------------
# User Management (Admin)
# ----------------------

class UserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAdminUser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['email', 'first_name', 'last_name']
    ordering_fields = ['email', 'first_name', 'last_name', 'role']

    def get_queryset(self):
        queryset = super().get_queryset()
        role = self.request.query_params.get('role')
        if role in ['vendor', 'customer', 'admin']:
            queryset = queryset.filter(role=role)
        return queryset



class CustomerListViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.filter(role=UserRole.CUSTOMER.value).order_by("-created_at")
    serializer_class = CustomerListSerializer
    permission_classes = [permissions.IsAdminUser]

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["first_name", "last_name", "email"]
    filterset_fields = ["role"]
    ordering_fields = ["created_at", "last_login"]


class VendorListViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.filter(role=UserRole.VENDOR.value).order_by("-created_at")
    serializer_class = VendorListSerializer
    permission_classes = [permissions.IsAdminUser]

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["first_name", "last_name", "email"]
    filterset_fields = ["role"]
    ordering_fields = ["created_at"]
