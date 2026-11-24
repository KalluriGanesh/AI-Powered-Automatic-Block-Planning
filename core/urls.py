from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.section_list, name='section_list'),
    path('sections/', views.section_list, name='section_list_alt'),
    path('sections/<str:code>/', views.section_detail, name='section_detail'),
    path('assets/', views.asset_list, name='asset_list'),
]
