from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Users
from users.views import (
    SellerApplicationView,
    SellerApplicationViewSet,
    UserLoginView,
    CustomerSignupView,
    UserProfileView,
    UserProfileUpdateView,
    ForgotPasswordRequestView,
    ForgotPasswordConfirmView,
    CustomerListViewSet,
    VendorListViewSet,
    UserListView
)

# Products
from products.views import (
    ProductViewSet,
    ProductImageViewSet,
    ReturnProductViewSet,
    TopSellProductViewSet,
    PromotionViewSet,
    VendorProductList,
    DeliveredOrderItemViewSet
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
)

# Dashboard
from dashboard.views import (
    VendorDashboardView,
    VendorSalesOverviewView,
    VendorPaymentsStatsView,
    VendorSalesPerformanceView,
    PayoutRequestViewSet,
    DashboardStatsView,
    SalesOverviewView,
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
    OrderItemViewSet
)

# Payments
from payments.views import (
    StripeWebhookView,
    CheckoutViewSet,
)

# Terms
from terms.views import (
    AdminTermsViewSet,
    PrivacyPolicyView,
    TermsConditionView,
)

# Chat
# from chat import views as chat_views


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



# Checkout (Stripe)
router.register("checkout", CheckoutViewSet, basename="checkout")

# Dashboard / Payouts
router.register("payouts", PayoutRequestViewSet, basename="payout")



router.register("admin/vendor-performance", VendorPerformanceViewSet, basename="vendor-performance")

router.register('shipping-addresses', ShippingAddressViewSet, basename='shipping-address')

# -------- URL Patterns --------
urlpatterns = [
    # Auth & Profile
    path("login/", UserLoginView.as_view(), name="user-login"),
    path("signup/customer/", CustomerSignupView.as_view(), name="signup-customer"),
    path("seller/apply/", SellerApplicationView.as_view(), name="seller-application-create"),
    path("profile/", UserProfileView.as_view(), name="user-profile"),
    path("profile/update/", UserProfileUpdateView.as_view(), name="profile-update"),
    path("forgot-password/request/", ForgotPasswordRequestView.as_view(), name="forgot-password-request"),
    path("forgot-password/confirm/", ForgotPasswordConfirmView.as_view(), name="forgot-password-confirm"),

    # Orders
    # path("orders/add-shipping-address/", AddShippingAddressView.as_view(), name="add-shipping-address"),
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

    # Chat
    # path("list_user_chats/", chat_views.UserChatsListView.as_view(), name="list-user-chats"),
    # path("history/<int:pk>/", chat_views.ChatMessagesListView.as_view(), name="get-chat-messages"),
    # path("message/<int:pk>/delete/", chat_views.MessageDeleteView.as_view(), name="delete-message"),
    # path("message/<int:pk>/edit/", chat_views.MessageUpdateView.as_view(), name="edit-message"),

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

    
    # Include router URLs
    path("", include(router.urls)),
]
