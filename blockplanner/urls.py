"""
Root URL configuration for blockplanner project.
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('dashboard.urls')),
    path('core/', include('core.urls')),
    path('requests/', include('requests_app.urls')),
    path('planner/', include('planner.urls')),
    path('ai/', include('ai.urls')),
]
