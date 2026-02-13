from django.urls import path
from .views import *
urlpatterns = [
    path('cnote/manage/',cnote_manage_view,name='cnote_manage'),
    path("cnotes/edit/<int:pk>/", cnote_manage_view, name="cnote_edit"),
    path("get-consignor-items/<int:consignor_id>/", get_consignor_items, name="get_consignor_items"),
    path('get-branch-by-location/<int:location_id>/', get_branch_by_location),
    path('get-quotation-rates/<int:consignor_id>/<int:location_id>/',get_quotation_rates,name='get_quotation_rates'),
    path("cnote/download-excel/",download_cnote_excel,name="download_cnote_excel"),
    path('cnote/list/',cnote_list_view,name='cnote_list'),
    path('cnote/print/<int:cnote_id>/',print_cnote,name="print_cnote"),
    path('cnote/delete/',cnote_cancel,name='cnote_cancel'),
    path('cnote/<int:pk>/', cnote_detail, name='cnote_detail'),
    path("cnote/receive/<int:pk>/", receive_cnote, name="receive_cnote"),
    path('manifest/manage/',manifest_manage,name='manifest_manage'),
    path('get-consignee-phone/', get_consignee_phone, name='get_consignee_phone'),
    path('add-receiver-ajax/', add_receiver_ajax, name='add_receiver_ajax'),
    path("add-shipper-ajax/", add_shipper_ajax, name="add_shipper_ajax"),
    path('manifest/list/', manifest_list, name='manifest_list'),
    path('manifest/edit/<int:manifest_id>/',manifest_edit,name="manifest_edit"),
    path('manifest/print/<int:manifest_id>/',print_manifest,name="manifest_print"),
    path("manifest/drs/<int:manifest_id>/",manifest_drs_update,name="manifest_drs_update"),
    path("get-lr-charge/",get_lr_charge, name="get_lr_charge"),
    path("report/booking",booking_report,name="booking_report"),
    path("report/daily",daily_booking_report,name="daily_report"),
    path('report/data',booking_data,name="booking_data"),
    path("booking/excel/", booking_excel, name="booking_excel"),
    path('branch/<int:branch_id>/commission/',branch_commission, name="branch_commission"),
    path("branch/<int:branch_id>/view-commission/",branch_commission_view,name="branch_view_commission"),
    path('cnote/commission',cnote_commission_view,name="cnote_commission")


]
