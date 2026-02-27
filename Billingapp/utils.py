# BillingApp/utils.py
from Accountapp.models import CourierShipment, CnoteBilling
from .models import Ledger

def get_ledger_balance(ledger_id):
    ledger = Ledger.objects.get(pk=ledger_id)
    shipments_total = sum(s.total_amount() for s in CourierShipment.objects.filter(consignor__billing_consignor_id=ledger_id))
    cnote_total = sum(c.total_amount() for c in CnoteBilling.objects.filter(consignor__billing_consignor_id=ledger_id))
    payments_credit = sum(p.amount for p in ledger.payment_set.filter(payment_type='Credit'))
    payments_debit = sum(p.amount for p in ledger.payment_set.filter(payment_type='Debit'))
    balance = ledger.opening_balance + shipments_total + cnote_total + payments_credit - payments_debit
    return balance