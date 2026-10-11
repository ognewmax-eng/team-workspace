from django.urls import path
from . import views
urlpatterns = [
    path('', views.document_list_view, name='document_list'),
    path('add/', views.document_create_view, name='document_create'),
    path('<int:pk>/', views.document_detail_view, name='document_detail'),
    path('<int:pk>/edit/', views.document_create_view, name='document_update'),
    path('<int:pk>/delete/', views.document_delete_view, name='document_delete'),
    path('<int:pk>/restore/', views.document_restore_view, name='document_restore'),
]
