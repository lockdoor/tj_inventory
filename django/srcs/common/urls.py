from django.urls import path
from django.contrib.auth import views as auth_views
from common import views

app_name = 'common'

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(template_name='common/login.html', redirect_authenticated_user=True), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # Company CRUD
    path('companies/', views.CompanyListView.as_view(), name='company-list'),
    path('companies/create/', views.CompanyCreateView.as_view(), name='company-create'),
    path('companies/trash/', views.CompanyTrashListView.as_view(), name='company-trash'),
    path('companies/<str:code>/', views.CompanyDetailView.as_view(), name='company-detail'),
    path('companies/<str:code>/update/', views.CompanyUpdateView.as_view(), name='company-update'),
    path('companies/<str:code>/delete/', views.CompanyDeleteView.as_view(), name='company-delete'),
    path('companies/<str:code>/restore/', views.CompanyRestoreView.as_view(), name='company-restore'),

    # Individual CRUD
    path('individuals/', views.IndividualListView.as_view(), name='individual-list'),
    path('individuals/create/', views.IndividualCreateView.as_view(), name='individual-create'),
    path('individuals/trash/', views.IndividualTrashListView.as_view(), name='individual-trash'),
    path('individuals/<int:pk>/', views.IndividualDetailView.as_view(), name='individual-detail'),
    path('individuals/<int:pk>/update/', views.IndividualUpdateView.as_view(), name='individual-update'),
    path('individuals/<int:pk>/delete/', views.IndividualDeleteView.as_view(), name='individual-delete'),
    path('individuals/<int:pk>/restore/', views.IndividualRestoreView.as_view(), name='individual-restore'),
]
