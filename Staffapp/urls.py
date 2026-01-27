from django.urls import path
from .views import *
urlpatterns = [
    path('cnote/manage/',cnote_manage_view,name='cnote_manage'),
    path("get-consignor-items/<int:consignor_id>/", get_consignor_items, name="get_consignor_items"),
    path('get-branch-by-location/<int:location_id>/', get_branch_by_location),
    path('get-quotation-rates/<int:consignor_id>/<int:location_id>/',get_quotation_rates,name='get_quotation_rates'),
    path("cnote/download-excel/",download_cnote_excel,name="download_cnote_excel"),
    path('cnote/list/',cnote_list_view,name='cnote_list'),
    path('cnote/print/<int:cnote_id>/',print_cnote,name="print_cnote")
]
