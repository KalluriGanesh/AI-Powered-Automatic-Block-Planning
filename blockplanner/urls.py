"""
Root URL configuration for blockplanner project.
"""

from django.contrib import admin
from django.urls import include, path
from core import views as core_views

urlpatterns = [
    path('admin/', admin.site.urls),

    # Top-level direct shortcuts for authentication & account
    path('account/', core_views.account_view, name='account_root'),
    path('login/', core_views.login_view, name='login_root'),
    path('signup/', core_views.signup_view, name='signup_root'),
    path('logout/', core_views.logout_view, name='logout_root'),

    # App namespaces
    path('', include('dashboard.urls')),
    path('core/', include('core.urls')),
    path('requests/', include('requests_app.urls')),
    path('planner/', include('planner.urls')),
    path('ai/', include('ai.urls')),
]
