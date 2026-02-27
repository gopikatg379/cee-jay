# BillingApp/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('groups/', views.group_list, name='group_list'),
    path('groups/add/', views.add_group, name='add_group'),
    path('ledgers/', views.ledger_list, name='ledger_list'),
    path('ledgers/add/', views.add_ledger, name='add_ledger'),
    path('ledger/<int:ledger_id>/', views.ledger_page, name='ledger_page'),
    path('payments/', views.payment_list, name='payment_list'),
    path('payments/add/', views.add_payment, name='add_payment'),
    path('ledger/<int:ledger_id>/balance/', views.ledger_balance, name='ledger_balance'),
    path('trial-balance/', views.trial_balance, name='trial_balance'),
    path('profit-loss/', views.profit_loss, name='profit_loss'),
    path('balance-sheet/', views.balance_sheet, name='balance_sheet'),
    path('vouchers/add/', views.add_entry, name='add_voucher'),
    path('vouchers/',views.voucher_list,name='voucher_list'),
    path('ledger/delete/<int:id>',views.delete_ledger,name='ledger_delete'),
    path('group/<int:group_id>/ledgers/', views.group_ledgers, name='group_ledgers'),
]