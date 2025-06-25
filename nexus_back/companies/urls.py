from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from . import bridge_views

app_name = 'companies'

router = DefaultRouter()
router.register(r'companies', views.CompanyViewSet, basename='company')
router.register(r'invitations', views.CompanyInvitationViewSet, basename='invitation')
router.register(r'bridge-configs', bridge_views.CompanyBridgeConfigurationViewSet, basename='bridge-config')

urlpatterns = [
    path('', include(router.urls)),
]
