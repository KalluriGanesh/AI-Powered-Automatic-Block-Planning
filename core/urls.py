from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # Railway Corridor & Asset URLs
    path('', views.section_list, name='section_list'),
    path('sections/', views.section_list, name='section_list_alt'),
    path('sections/<str:code>/', views.section_detail, name='section_detail'),
    path('assets/', views.asset_list, name='asset_list'),

    # User Account & Authentication URLs
    path('account/', views.account_view, name='account'),
    path('login/', views.login_view, name='login'),
    path('signup/', views.signup_view, name='signup'),
    path('logout/', views.logout_view, name='logout'),
]
