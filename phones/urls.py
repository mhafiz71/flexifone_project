from django.urls import path
from . import views

app_name = 'phones'

urlpatterns = [
    path('', views.phone_list, name='phone_list'),
    path('add/', views.phone_create, name='phone_create'),
    path('<slug:slug>/', views.phone_detail, name='phone_detail'),
    path('<slug:slug>/update/', views.phone_update, name='phone_update'),
    path('<slug:slug>/delete/', views.phone_delete, name='phone_delete'),
    path('<slug:slug>/buy-on-credit/', views.buy_on_credit, name='buy_on_credit'),
]