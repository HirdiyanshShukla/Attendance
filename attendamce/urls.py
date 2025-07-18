from  django.urls import path
from . import views

urlpatterns = [
    path('', views.mainPage, name='mainhomePage'),
    path('home/', views.home, name='homePage'),
]