from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Users
from users.views import (
    SellerApplicationView,
    SellerApplicationViewSet,
    CustomerSignupView,
    UserProfileView,
    UserProfileUpdateView,
    CustomerListViewSet,
    VendorListViewSet,
    UserListView,
    UnifiedLoginView,
    BulkSellerApplicationStatusUpdateView,
    BulkUserActivateView,
    BulkUserDeleteView,
    ChangePasswordView,
    SetNewPasswordView,
    SendPasswordResetOTPView,
    VerifyPasswordResetOTPView,
    
)

# Products
from products.views import (
    ProductViewSet,
    ProductImageViewSet,
    ReturnProductViewSet,
    TopSellProductViewSet,
    PromotionViewSet,
    VendorProductList,
    DeliveredOrderItemViewSet,
    BulkProductsStatusUpdateViewSet
)

# Common
from common.views import (
    CategoryViewSet,
    TagViewSet,
    SEOViewSet,
    SavedProductViewSet,
    ReviewViewSet,
    OrderManagementViewSet,
    BannerViewSet,
    WishlistViewSet,)

# Dashboard
from dashboard.views import (
    VendorDashboardView,
    VendorSalesOverviewView,
    VendorPaymentsStatsView,
    VendorSalesPerformanceView,
    PayoutRequestViewSet,
    DashboardStatsView,
    LatestOrdersView, 
    LowStockAlertsView,
    VendorPerformanceViewSet,
    FurnitureSalesComparisonView,
    CategorySalesView,
    TopSellProductGraphView,
)

# Orders
from orders.views import (
    OrderViewSet,
    ShippingAddressViewSet,
    CartViewSet,
    OrderReceiptView,
    OrderItemViewSet,
    BulkOrderStatusUpdateView
)

# Payments
from payments.views import (
    StripeWebhookView,
    CheckoutViewSet,
    BulkPaymentStatusUpdateView
)

# Terms
from terms.views import (
    AdminTermsViewSet,
    PrivacyPolicyView,
    TermsConditionView,
)


# -------- Router config --------
router = DefaultRouter()

# Common
router.register("categories", CategoryViewSet, basename="category")
router.register("tags", TagViewSet, basename="tag")
router.register("seo", SEOViewSet, basename="seo")
router.register("saved-products", SavedProductViewSet, basename="saved-product")
router.register("product-reviews", ReviewViewSet, basename="product-review")
router.register("admin/policies", AdminTermsViewSet, basename="admin-policies")
router.register("admin/banners", BannerViewSet, basename="banner")




# Products
router.register("products", ProductViewSet, basename="product")
router.register("product-images", ProductImageViewSet, basename="product-image")
router.register("top-sell-products", TopSellProductViewSet, basename="top-sell-product")
router.register("promotions", PromotionViewSet, basename="promotion")
router.register("vendor/products", VendorProductList, basename="vendor-products")
router.register("returns/product", ReturnProductViewSet, basename="return-product")
router.register("deliverd/item", DeliveredOrderItemViewSet, basename="deliverd-product")




# Users
router.register("seller/applications", SellerApplicationViewSet, basename="seller-application")
router.register("customers", CustomerListViewSet, basename="customers")
router.register("vendors", VendorListViewSet, basename="vendors")
router.register("users", UserListView, basename="user")


# Orders & Cart
router.register("orders", OrderViewSet, basename="order")
router.register("cart", CartViewSet, basename="cart")
router.register("vendor/order/list", OrderManagementViewSet, basename="order-manage")
router.register("order-items", OrderItemViewSet, basename="order-item")



router.register("checkout", CheckoutViewSet, basename="checkout")
router.register("payouts", PayoutRequestViewSet, basename="payout")
router.register('wishlist', WishlistViewSet, basename='wishlist')
router.register("admin/vendor-performance", VendorPerformanceViewSet, basename="vendor-performance")
router.register('shipping-addresses', ShippingAddressViewSet, basename='shipping-address')



urlpatterns = [

    path("login/", UnifiedLoginView.as_view(), name="user-login"),
    path("signup/customer/", CustomerSignupView.as_view(), name="signup-customer"),
    path("seller/apply/", SellerApplicationView.as_view(), name="seller-application-create"),
    path("profile/", UserProfileView.as_view(), name="user-profile"),
    path("profile/update/", UserProfileUpdateView.as_view(), name="profile-update"),
    # path("forgot-password/request/", ForgotPasswordRequestView.as_view(), name="forgot-password-request"),
    # path("forgot-password/confirm/", ForgotPasswordVerifyView.as_view(), name="forgot-password-confirm"),
    # path("forgot-password/reset/", ResetPasswordView.as_view(), name="reset-password"),

    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('set-new-password/', SetNewPasswordView.as_view(), name='set-new-password'),
    # path('auth/send-verification-otp/', SendVerificationOTPView.as_view(), name='send-verification-otp'),
    # path('auth/verify-account/', VerifyAccountOTPView.as_view(), name='verify-account'),
    path('send-reset-otp/', SendPasswordResetOTPView.as_view(), name='send-reset-otp'),
    path('verify-reset-otp/', VerifyPasswordResetOTPView.as_view(), name='verify-reset-otp'),


    path("receipt/<str:order_id>/", OrderReceiptView.as_view(), name="order-receipt"),

    # Vendor Dashboard
    path("vendor/dashboard/", VendorDashboardView.as_view(), name="vendor-dashboard"),
    path("vendor/sales-overview/", VendorSalesOverviewView.as_view(), name="vendor-sales-overview"),
    path("vendor/payments-stats/", VendorPaymentsStatsView.as_view(), name="vendor-payments-stats"),
    path("vendor/sales-performance/", VendorSalesPerformanceView.as_view(), name="vendor-sales-performance"),

    # Terms & Privacy
    path("terms/", TermsConditionView.as_view(), name="terms-condition"),
    path("privacy/", PrivacyPolicyView.as_view(), name="privacy-policy"),

    # Stripe webhook
    path("stripe/webhook/", StripeWebhookView.as_view(), name="stripe-webhook"),

    path("admin/stats/", DashboardStatsView.as_view(), name="dashboard-stats"),
    path("admin/top/sell/products/", TopSellProductGraphView.as_view(), name="sell-product-graph"),
    path("top-sell-products/", TopSellProductGraphView.as_view(), name="sell-product-graph"),
    path("admin/alerts/low-stock/", LowStockAlertsView.as_view(), name="low-stock-alerts"),
    #  http://10.10.13.16:2500/api/admin/sales-overview/?range=1y
    #  http://10.10.13.16:2500/api/admin/sales-overview/?range=30d
    #  http://10.10.13.16:2500/api/admin/sales-overview/?range=7d
    

    path("admin/latest-orders/", LatestOrdersView.as_view(), name="latest-orders"),
    path("admin/furniture-sales-comparison/", FurnitureSalesComparisonView.as_view(), name="furniture-sales-comparison"),
    path("admin/category-sales/", CategorySalesView.as_view(), name="category-sales"),


    # Bulk Operations
    path("admin/bulk/seller-applications/status/", BulkSellerApplicationStatusUpdateView.as_view(), name="bulk-seller-application-status"),
    path("admin/bulk/users/activate/", BulkUserActivateView.as_view(), name="bulk-user-activate"),
    path("admin/bulk/users/delete/", BulkUserDeleteView.as_view(), name="bulk-user-delete"),
    path("admin/bulk/products/status/", BulkProductsStatusUpdateViewSet.as_view({'post': 'update_status'}), name="bulk-product-status"),
    path("admin/bulk/orders/status/", BulkOrderStatusUpdateView.as_view(), name="bulk-order-status"),
    path("admin/bulk/payments/status/", BulkPaymentStatusUpdateView.as_view(), name="bulk-payment-status"),


    # Include router URLs
    path("", include(router.urls)),
]
