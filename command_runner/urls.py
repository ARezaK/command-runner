from django.urls import path
from .views import command_list, start_command, command_status

app_name = 'command_runner'

urlpatterns = [
    path('', command_list, name='command_list'),
    path('start/', start_command, name='start_command'),
    path('status/<str:command_id>/', command_status, name='command_status'),
]