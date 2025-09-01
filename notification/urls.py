from django.core.management.commands.runserver import naiveip_re
from django.urls import path
from django.conf import settings
from . import views
from rest_framework.routers import DefaultRouter




router = DefaultRouter()

router.register('order-notifications', views.OrderNotifyViewSet, basename='order-notification')

urlpatterns = [

    path('notification/list/', views.notification_list, name='notification-list'),
    path('notification/unseen/', views.unseen_notification_list, name='unseen-notification-list'),
    path('<int:pk>/seen/', views.mark_notification_seen, name='mark-notification-seen'),
    path('<int:pk>/delete/', views.NotificationDeleteAPIView.as_view(), name='delete-notification')
    
]

if settings.DEBUG:
    urlpatterns += [
        path('hit_notify/<str:email>/', views.hit_notify),
    ]
