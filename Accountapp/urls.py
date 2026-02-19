from django.urls import path
from .views import *
urlpatterns = [
    path("dashboard",accounts_dashboard,name="accounts_dashboard"),
    path("billing/consignor/manage",billing_consignor_manage,name="billing_shipper_manage"),
    path("billing/consignor/add",billing_consignor_manage,name="billing_shipper_add"),
    path("billing/consignor/edit/<int:billing_consignor_id>",billing_consignor_manage,name="billing_shipper_edit"),
    path("billing/consignor/delete/<int:billing_consignor_id>",billing_consignor_delete,name="billing_shipper_delete"),
    path("billing/consignee/manage",billing_consignee_manage,name="billing_receiver_manage"),
    path("billing/consignee/add",billing_consignee_manage,name="billing_receiver_add"),
    path("billing/consignee/edit/<int:billing_consignee_id>",billing_consignee_manage,name="billing_receiver_edit"),
    path("billing/consignee/delete/<int:billing_consignee_id>",billing_consignee_delete,name="billing_receiver_delete"),
    path("billing/consignor/excel",billing_consignor_excel,name="billing_shipper_export_excel"),
    path("billing/courier/manage",courier_manage,name="courier_manage"),
    path("billing/courier/add",courier_manage,name="courier_add"),
    path("billing/courier/edit/<int:id>",courier_manage,name="courier_edit"),
    path("billing/courier/delete/<int:id>",courier_delete,name="courier_delete"),
    path("billing/create/", create_billing, name="create_billing"),

]