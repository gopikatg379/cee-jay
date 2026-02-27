from django.contrib import messages
from django.shortcuts import render, redirect,get_object_or_404
from .models import *
from django.db.models import Sum
from .utils import get_ledger_balance
from django.db import transaction
import uuid
from decimal import Decimal
from itertools import groupby
from django.http import JsonResponse
from django.db.models import Q
from Accountapp.models import Invoice
def add_group(request):
    if request.method == "POST":
        Groups.objects.create(
            group_name=request.POST['name'],
            under=request.POST['under'],
        )
        return redirect('group_list')
    return render(request, 'billing/add_group.html')

def group_list(request):
    groups = Groups.objects.all()
    return render(request, 'billing/group_list.html', {'groups': groups})


def ledger_list(request):
    ledgers = Ledger.objects.all()
    ledger_data = []

    for ledger in ledgers:
        debit_sum = Entry.objects.filter(ledger=ledger).aggregate(total=Sum('debit'))['total'] or 0
        credit_sum = Entry.objects.filter(ledger=ledger).aggregate(total=Sum('credit'))['total'] or 0
        current_balance = ledger.opening_balance + debit_sum - credit_sum

        entries = Entry.objects.filter(ledger=ledger).order_by('date')
        running_balance = ledger.opening_balance
        transactions = []
        for e in entries:
            running_balance += e.debit - e.credit
            transactions.append({
                'date': e.date,
                'debit': e.debit,
                'credit': e.credit,
                'balance': running_balance
            })

        ledger_data.append({
            'ledger': ledger,
            'current_balance': current_balance,
            'transactions': transactions
        })

    context = {'ledger_data': ledger_data}
    return render(request, 'billing/ledger_list.html', context)

def add_ledger(request):
    groups = Groups.objects.all()
    if request.method == "POST":
        Ledger.objects.create(
            ledger_name=request.POST['name'],
            group=Groups.objects.get(id=request.POST['group']),
            opening_balance=request.POST.get('opening_balance', 0)
        )
        return redirect('ledger_list')
    return render(request, 'billing/add_ledger.html',{'groups':groups,})

def delete_ledger(request,id):
    ledger = get_object_or_404(Ledger,id=id)
    ledger.delete()
    return redirect('ledger_list')

def payment_list(request):
    payments = Payment.objects.all()
    return render(request, 'billing/payment_list.html', {'payments': payments})

def add_payment(request):
    ledgers = Ledger.objects.all()
    if request.method == "POST":
        Payment.objects.create(
            ledger_id=request.POST['ledger'],
            payment_type=request.POST['payment_type'],
            amount=request.POST['amount'],
            date=request.POST['date'],
            mode=request.POST.get('mode', ''),
            remarks=request.POST.get('remarks', '')
        )
        return redirect('payment_list')
    return render(request, 'billing/add_payment.html', {'ledgers': ledgers})

def ledger_balance(request, ledger_id):
    ledger = Ledger.objects.get(id=ledger_id)
    balance = get_ledger_balance(ledger_id)
    return render(request, 'billing/ledger_balance.html', {'ledger': ledger, 'balance': balance})

def ledger_page(request, ledger_id):
    ledger = get_object_or_404(Ledger, id=ledger_id)

    from_date = request.GET.get("from_date")
    to_date = request.GET.get("to_date")

    entries = Entry.objects.filter(ledger=ledger)

    if from_date and to_date:
        entries = entries.filter(date__range=[from_date, to_date])

    total_debit = sum(e.debit for e in entries)
    total_credit = sum(e.credit for e in entries)
    running_balance = ledger.opening_balance
    entry_data = []
    for e in entries:
        running_balance += e.debit - e.credit
        entry_data.append({
            "date": e.date,
            "debit": e.debit,
            "credit": e.credit,
            "remarks": e.remarks,
            "invoice": e.invoice,
            "closing_balance": running_balance
        })
    return render(request, "billing/ledger_page.html", {
        "ledger": ledger,
        "entries": entry_data,
        "from_date": from_date,
        "to_date": to_date,
        "total_debit": total_debit,
        "total_credit": total_credit,
    })

def add_entry(request):
    ledgers = Ledger.objects.all()

    if request.method == "POST":
        date = request.POST.get("date")
        voucher_type = request.POST.get("voucher_type")
        transaction_id = str(uuid.uuid4())
        remarks = request.POST.get("remarks")
        if voucher_type in ["Payment", "Receipt", "Contra"]:
            account_id = request.POST.get("from_ledger")
            particular_id = request.POST.get("to_ledger")
            amount = request.POST.get("amount")

            try:
                amount = Decimal(amount)
                if amount <= 0:
                    raise ValueError
            except:
                messages.error(request, "Invalid Amount")
                return redirect("add_entry")

            if account_id == particular_id:
                messages.error(request, "Account and Particular cannot be same.")
                return redirect("add_entry")

            account_ledger = Ledger.objects.get(id=account_id)
            particular_ledger = Ledger.objects.get(id=particular_id)

            

            with transaction.atomic():
                if voucher_type == "Payment":

                    Entry.objects.create(
                        date=date,
                        ledger=particular_ledger,
                        debit=amount,
                        credit=0,
                        voucher_type=voucher_type,
                        transaction_id=transaction_id,
                        remarks=remarks
                    )

                    Entry.objects.create(
                        date=date,
                        ledger=account_ledger,
                        debit=0,
                        credit=amount,
                        voucher_type=voucher_type,
                        transaction_id=transaction_id,
                        remarks=remarks
                    )

                elif voucher_type == "Receipt":

                    Entry.objects.create(
                        date=date,
                        ledger=account_ledger,
                        debit=amount,
                        credit=0,
                        voucher_type=voucher_type,
                        transaction_id=transaction_id,
                        remarks=remarks
                    )

                    Entry.objects.create(
                        date=date,
                        ledger=particular_ledger,
                        debit=0,
                        credit=amount,
                        voucher_type=voucher_type,
                        transaction_id=transaction_id,
                        remarks=remarks
                    )

                elif voucher_type == "Contra":

                    Entry.objects.create(
                        date=date,
                        ledger=account_ledger,
                        debit=0,
                        credit=amount,
                        voucher_type=voucher_type,
                        transaction_id=transaction_id,
                        remarks=remarks
                    )


                    Entry.objects.create(
                        date=date,
                        ledger=particular_ledger,
                        debit=amount,
                        credit=0,
                        voucher_type=voucher_type,
                        transaction_id=transaction_id,
                        remarks=remarks
                    )
        elif voucher_type == "Journal":

            ledger_ids = request.POST.getlist("ledger[]")
            debits = request.POST.getlist("debit[]")
            credits = request.POST.getlist("credit[]")

            total_debit = 0
            total_credit = 0

            for d, c in zip(debits, credits):
                total_debit += Decimal(d or 0)
                total_credit += Decimal(c or 0)

            if total_debit == 0 or total_credit == 0:
                messages.error(request, "Debit and Credit cannot be zero.")
                return redirect("add_entry")

            if round(total_debit, 2) != round(total_credit, 2):
                messages.error(request, "Total Debit and Credit must be equal.")
                return redirect("add_entry")

            for ledger_id, debit, credit in zip(ledger_ids, debits, credits):

                debit = Decimal(debit or 0)
                credit = Decimal(credit or 0)

                if debit == 0 and credit == 0:
                    continue

                Entry.objects.create(
                    date=date,
                    ledger=Ledger.objects.get(id=ledger_id),
                    debit=debit,
                    credit=credit,
                    voucher_type=voucher_type,
                    transaction_id=transaction_id,
                    remarks=remarks
                )
        messages.success(request, "Voucher recorded successfully.")
        return redirect("voucher_list")

    return render(request, "billing/add_entry.html", {"ledgers": ledgers})
def voucher_list(request):
    entries = Entry.objects.all().order_by('-date', 'transaction_id')

    vouchers = []

    for transaction_id, group in groupby(entries, key=lambda x: x.transaction_id):
        group_list = list(group)

        vouchers.append({
            "transaction_id": transaction_id,
            "date": group_list[0].date,
            "voucher_type": group_list[0].voucher_type,
            "entries": group_list,
            "total_debit": sum(e.debit for e in group_list),
            "total_credit": sum(e.credit for e in group_list),
        })

    return render(request, "billing/voucher_list.html", {"vouchers": vouchers})


def trial_balance(request):
    ledgers = Ledger.objects.all()
    data = []

    total_debit = 0
    total_credit = 0

    for ledger in ledgers:
        debit_sum = Entry.objects.filter(ledger=ledger).aggregate(Sum('debit'))['debit__sum'] or 0
        credit_sum = Entry.objects.filter(ledger=ledger).aggregate(Sum('credit'))['credit__sum'] or 0

        closing = ledger.opening_balance + debit_sum - credit_sum

        if closing >= 0:
            debit = closing
            credit = 0
        else:
            debit = 0
            credit = abs(closing)

        total_debit += debit
        total_credit += credit

        data.append({
            'name': ledger.ledger_name,
            'debit': debit,
            'credit': credit
        })

    return render(request, 'billing/trial_balance.html', {
        'data': data,
        'total_debit': total_debit,
        'total_credit': total_credit
    })


def profit_loss(request):
    income_groups = Groups.objects.filter(under='Income')
    expense_groups = Groups.objects.filter(under='Expense')

    income_data = []
    expense_data = []

    total_income = 0
    total_expense = 0

    # --- Income Groups ---
    for group in income_groups:
        ledgers = Ledger.objects.filter(group=group)
        group_total = 0
        ledger_list = []

        for ledger in ledgers:
            # For each ledger, fetch individual customers/entries
            credit = Entry.objects.filter(ledger=ledger).aggregate(Sum('credit'))['credit__sum'] or 0
            debit = Entry.objects.filter(ledger=ledger).aggregate(Sum('debit'))['debit__sum'] or 0
            ledger_balance = credit - debit
            group_total += ledger_balance

            # Sub-entries under ledger
            entries = Entry.objects.filter(ledger=ledger)
            entry_list = []
            for e in entries:
                entry_list.append({
                    'customer': e.customer.name if hasattr(e, 'customer') else 'N/A',
                    'amount': e.credit - e.debit
                })

            ledger_list.append({
                'id': ledger.id,
                'ledger_name': ledger.ledger_name,
                'amount': ledger_balance,
                'entries': entry_list
            })

        total_income += group_total
        income_data.append({
            'group_name': group.group_name,
            'group_total': group_total,
            'ledgers': ledger_list
        })

    # --- Expenses Groups ---
    for group in expense_groups:
        ledgers = Ledger.objects.filter(group=group)
        group_total = 0
        ledger_list = []

        for ledger in ledgers:
            debit = Entry.objects.filter(ledger=ledger).aggregate(Sum('debit'))['debit__sum'] or 0
            credit = Entry.objects.filter(ledger=ledger).aggregate(Sum('credit'))['credit__sum'] or 0
            ledger_balance = debit - credit
            group_total += ledger_balance

            entries = Entry.objects.filter(ledger=ledger)
            entry_list = []
            for e in entries:
                entry_list.append({
                    'customer': e.customer.name if hasattr(e, 'customer') else 'N/A',
                    'amount': e.debit - e.credit
                })

            ledger_list.append({
                'id': ledger.id,
                'ledger_name': ledger.ledger_name,
                'amount': ledger_balance,
                'entries': entry_list
            })

        total_expense += group_total
        expense_data.append({
            'group_name': group.group_name,
            'group_total': group_total,
            'ledgers': ledger_list
        })

    net_profit = total_income - total_expense

    return render(request, 'billing/profit_loss.html', {
        'income_data': income_data,
        'expense_data': expense_data,
        'total_income': total_income,
        'total_expense': total_expense,
        'net_profit': net_profit
    })
def balance_sheet(request):

    asset_groups = Groups.objects.filter(under='Asset')
    liability_groups = Groups.objects.filter(under='Liability')

    asset_data = []
    liability_data = []

    total_assets = 0
    total_liabilities = 0

    # -------- ASSETS --------
    for group in asset_groups:
        ledgers = Ledger.objects.filter(group=group)

        group_total = 0
        ledger_list = []

        for ledger in ledgers:
            debit = Entry.objects.filter(ledger=ledger).aggregate(Sum('debit'))['debit__sum'] or 0
            credit = Entry.objects.filter(ledger=ledger).aggregate(Sum('credit'))['credit__sum'] or 0

            balance = ledger.opening_balance + debit - credit
            group_total += balance

            ledger_list.append({
                'id': ledger.id,
                'ledger_name': ledger.ledger_name,
                'amount': balance
            })

        total_assets += group_total

        asset_data.append({
            'group_name': group.group_name,
            'group_total': group_total,
            'ledgers': ledger_list
        })

    # -------- LIABILITIES --------
    for group in liability_groups:
        ledgers = Ledger.objects.filter(group=group)

        group_total = 0
        ledger_list = []

        for ledger in ledgers:
            credit = Entry.objects.filter(ledger=ledger).aggregate(Sum('credit'))['credit__sum'] or 0
            debit = Entry.objects.filter(ledger=ledger).aggregate(Sum('debit'))['debit__sum'] or 0

            balance = ledger.opening_balance + credit - debit
            group_total += balance

            ledger_list.append({
                'id': ledger.id,
                'ledger_name': ledger.ledger_name,
                'amount': balance
            })

        total_liabilities += group_total

        liability_data.append({
            'group_name': group.group_name,
            'group_total': group_total,
            'ledgers': ledger_list
        })

    return render(request, 'billing/balance_sheet.html', {
        'asset_data': asset_data,
        'liability_data': liability_data,
        'total_assets': total_assets,
        'total_liabilities': total_liabilities
    })

def group_ledgers(request, group_id):
    group = get_object_or_404(Groups, id=group_id)
    ledgers = Ledger.objects.filter(group=group)

    ledger_data = []
    total_amount = 0

    for ledger in ledgers:
        debit = Entry.objects.filter(ledger=ledger).aggregate(Sum('debit'))['debit__sum'] or 0
        credit = Entry.objects.filter(ledger=ledger).aggregate(Sum('credit'))['credit__sum'] or 0

        if group.under == "Income":
            amount = credit - debit
        else:
            amount = debit - credit

        total_amount += amount
        ledger_data.append({'name': ledger.ledger_name, 'amount': amount})

    return render(request, 'billing/group_ledgers.html', {
        'group': group,
        'ledger_data': ledger_data,
        'total_amount': total_amount
    })