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
from sensors import views as sensor_views

urlpatterns = [

    # ── Admin Django ──────────────────────────────────────────
    path('admin/', admin.site.urls),
    

    # ── Pages HTML principales ────────────────────────────────
    path('',                    views.dashboard,      name='dashboard'),
    path('dashboard/',          views.dashboard,      name='dashboard_alt'),
    path('patients/',           views.patient_list,   name='patient_list'),
    path('patients/<str:patient_id>/', views.patient_detail, name='patient_detail'),
    path('geolocalisation/',    views.geolocation,    name='geolocation'),
    path('alertes/',            views.alertes,        name='alertes'),
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

    # ── Capteurs réels (ESP32 / Arduino) ──────────────────────
    path('api/recevoir/',       sensor_views.recevoir_donnees, name='api_recevoir'),
    path('api/sensors/ingest/', sensor_views.ingest_sensors, name='sensors_ingest'),
    path('api/sensors/latest/', sensor_views.latest_sensors, name='sensors_latest'),
    path('api/chutes/',         sensor_views.api_chutes,     name='api_chutes'),
    path('api/chutes/simulate/', sensor_views.simulate_fall, name='api_simulate_fall'),
    path('api/monitoring/active/', sensor_views.monitoring_active, name='monitoring_active'),
    path('api/notifications/',  sensor_views.api_notifications, name='api_notifications'),
    path('api/notifications/read/', sensor_views.mark_notifications_read, name='notifications_read'),
    path('api/messages/',       sensor_views.api_messages,   name='api_messages'),
    path('api/messages/send/',  sensor_views.send_message,   name='api_send_message'),
    path('api/sms/send/',       sensor_views.api_sms_send,   name='api_sms_send'),
    path('api/emails/',         sensor_views.api_emails,     name='api_emails'),
    path('api/family/inbox/',   sensor_views.api_family_inbox, name='api_family_inbox'),
    path('api/family/accounts/', sensor_views.api_family_accounts, name='api_family_accounts'),
    path('api/patient/inbox/',  sensor_views.api_patient_inbox,  name='api_patient_inbox'),
    path('api/portail/login/',  sensor_views.api_portail_login,  name='api_portail_login'),
    path('api/portail/credentials/', sensor_views.api_portail_credentials, name='api_portail_credentials'),
    path('api/movements/',      sensor_views.api_movements,  name='api_movements'),
]
