from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PostViewSet,
    CommentViewSet,
    register_view,
    login_view,
    logout_view,
    me_view,
    profile_update_view,
    user_activity_view,
    insights_view,
)

router = DefaultRouter()
router.register('posts', PostViewSet, basename='post')
router.register('comments', CommentViewSet, basename='comment')

urlpatterns = [
    path('api/auth/register/', register_view, name='auth-register'),
    path('api/auth/login/', login_view, name='auth-login'),
    path('api/auth/logout/', logout_view, name='auth-logout'),
    path('api/auth/me/', me_view, name='auth-me'),
    path('api/auth/profile/', profile_update_view, name='auth-profile-update'),
    path('api/auth/user-activity/', user_activity_view, name='auth-user-activity'),
    path('api/insights/', insights_view, name='admin-insights'),
    path('api/', include(router.urls)),
]

