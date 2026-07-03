"""
URL configuration for geriatrie_iot project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
# ============================================================
#  backend/geriatrie_iot/urls.py
#  Toutes les routes du projet
# ============================================================
from django.contrib import admin
from django.urls import path, include
from . import views

urlpatterns = [

    # ── Admin Django ──────────────────────────────────────────
    path('admin/', admin.site.urls),
    

    # ── Pages HTML principales ────────────────────────────────
    path('',                    views.dashboard,      name='dashboard'),
    path('dashboard/',          views.dashboard,      name='dashboard_alt'),
    path('patients/',           views.patient_list,   name='patient_list'),
    path('patients/<str:patient_id>/', views.patient_detail, name='patient_detail'),
    path('geolocalisation/',    views.geolocation,    name='geolocation'),
    path('analyse/',            views.analyse,        name='analyse'),
    # Portail usagers (famille + patient) — séparé de l'admin médecin
    path('portail/',            views.portail_login,   name='portail_login'),
    path('portail/famille/',    views.famille_espace,  name='portail_famille'),
    path('portail/patient/',    views.patient_espace,  name='portail_patient'),
    path('portail/carte/',      views.portail_carte,   name='portail_carte'),
    # Anciennes URLs → redirection
    path('famille/',            views.portail_login,   name='famille_login'),
    path('famille/espace/',     views.famille_espace,  name='famille_espace'),

    # ── API JSON (appelées par le JavaScript frontend) ────────
    path('api/patients/',       views.api_patients,         name='api_patients'),
    path('api/gps/',            views.api_gps,              name='api_gps'),
    path('api/stats/',          views.api_dashboard_stats,  name='api_stats'),

    # ── Apps séparées (si vous utilisez des apps Django) ─────
    # path('api/alerts/',  include('alerts.urls')),
    # path('api/sensors/', include('sensors.urls')),
]
