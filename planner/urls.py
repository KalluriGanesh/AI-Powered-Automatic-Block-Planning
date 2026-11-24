from django.urls import path
from . import views

app_name = 'planner'

urlpatterns = [
    path('', views.run_list, name='run_list'),
    path('generate/', views.generate_plan, name='generate_plan'),
    path('runs/<int:pk>/', views.run_detail, name='run_detail'),
    path('compare/', views.compare_plans, name='compare_plans'),
]
