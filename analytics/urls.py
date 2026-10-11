"""
URL маршруты для приложения analytics.
"""
from django.urls import path
from . import views

urlpatterns = [
    path('', views.analytics_dashboard_view, name='analytics_dashboard'),
    path('export/', views.analytics_export_view, name='analytics_export'),
]
