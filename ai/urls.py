from django.urls import path
from . import views

app_name = 'ai'

urlpatterns = [
    path('explain/<int:block_id>/', views.explain_view, name='explain_block'),
]
