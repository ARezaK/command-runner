from django.urls import path
from . import views

app_name = 'command_runner'

urlpatterns = [
    path('', views.command_list, name='command_list'),
    path('start/', views.start_command, name='start_command'),
    path('status/<str:command_id>/', views.command_status, name='command_status'),
]