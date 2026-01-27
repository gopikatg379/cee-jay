from django.shortcuts import render,redirect
from Adminapp.models import *
from .models import *
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.core.paginator import Paginator
from openpyxl import Workbook
from datetime import datetime
from django.http import HttpResponse
from django.template.loader import render_to_string


def get_consignor_items(request, consignor_id):
    consignor = get_object_or_404(Consignor, pk=consignor_id)

    consignor_items = consignor.items.all()

    if consignor_items.exists():
        data = [
            {
                "id": item.item_id,
                "name": item.item_name,
                "rate": 0 
            }
            for item in consignor_items
        ]
    else:
        default_items = Item.objects.filter(is_default=True)
        data = [
            {
                "id": item.item_id,
                "name": item.item_name,
                "rate": 0
            }
            for item in default_items
        ]

    return JsonResponse(data, safe=False)

def get_branch_by_location(request, location_id):
    try:
        location = Location.objects.get(location_id=location_id)
        print(location)
        branches = location.branch.all()
        print(branches)
        data = [
            {
                "branch_id": b.branch_id,
                "branch_name": b.branch_name
            }
            for b in branches
        ]

        return JsonResponse({"branches": data})

    except Location.DoesNotExist:
        return JsonResponse({"branches": []}, status=404)

@login_required(login_url='/')
def cnote_manage_view(request):
    user = request.user
    consignors = Consignor.objects.all()
    consignees = Consignee.objects.all()
    branches = Branch.objects.all()
    locations = Location.objects.all()
    items = Item.objects.all()
    if user.role == 'ADMIN':
        branches = Branch.objects.all()
    else:
        branches = Branch.objects.filter(branch_id=user.branch_id)
    if request.method == "POST":
        date = request.POST.get('date')
        reference_no = request.POST.get('reference_no')
        payment = request.POST.get('payment')
        consignor_id = request.POST.get('consignor')
        consignee_id = request.POST.get('consignee')
        branch_id = request.POST.get('branch')
        destination_id = request.POST.get('location')
        lr_charge = Decimal(request.POST.get('lr_charge') or 0)
        invoice_no = request.POST.get('invoice_no')
        invoice_amt = Decimal(request.POST.get('invoice_amt') or 0)
        pickup_charge = Decimal(request.POST.get('pickup_charge') or 0)
        hamali_charge = Decimal(request.POST.get('hamali_charge') or 0)
        unloading_charge = Decimal(request.POST.get('unloading_charge') or 0)
        door_delivery = Decimal(request.POST.get('door_delivery') or 0)
        other_charge = Decimal(request.POST.get('other_charge') or 0)
        delivery_type = request.POST.get('delivery_type')
        booking_branch = request.POST.get('booking_branch')
        items_ids = request.POST.getlist('item[]')
        qtys = request.POST.getlist('qty[]')
        rates = request.POST.getlist('rate[]')
        totals = request.POST.getlist('total[]')

        total_items = sum(int(q) for q in qtys if q)
        freight = sum(Decimal(t) for t in totals if t)
        grand_total = freight + lr_charge + pickup_charge + hamali_charge + unloading_charge + door_delivery + other_charge

        cnote = CnoteModel.objects.create(
            date=date,
            reference_no=reference_no,
            payment=payment,
            consignor_id=consignor_id,
            consignee_id=consignee_id,
            delivery_branch_id = branch_id,
            booking_branch_id=booking_branch,
            destination_id=destination_id,
            lr_charge=lr_charge,
            invoice_no=invoice_no,
            invoice_amt=invoice_amt,
            pickup_charge=pickup_charge,
            hamali_charge=hamali_charge,
            unloading_charge=unloading_charge,
            door_delivery=door_delivery,
            other_charge=other_charge,
            delivery_type=delivery_type,
            total_item=total_items,
            freight=freight,
            total=grand_total
        )

        for i, item_id in enumerate(items_ids):
            if item_id:
                CnoteItem.objects.create(
                    cnote=cnote,
                    item_id=item_id,
                    qty=int(qtys[i]),
                    rate=Decimal(rates[i]),
                    total=Decimal(totals[i])
                )

        return redirect('dashboard')

    context = {
        "consignors": consignors,
        "consignees": consignees,
        "branches": branches,
        "locations": locations,
        'items': items, 
    }
    return render(request, 'cnote_manage.html', context)


def get_quotation_rates(request, consignor_id, location_id):
    selected_location = Location.objects.get(location_id=location_id)

    quotations = Quotation.objects.filter(
        agent_id=consignor_id,
        location__district=selected_location.district 
    ).select_related('item')
    data = []
    for q in quotations:
        data.append({
            "item_id": q.item_id,
            "item_name": q.item.item_name,
            "rate": float(q.rate)
        })
    return JsonResponse(data, safe=False)

def cnote_list_view(request):

    cnotes = CnoteModel.objects.select_related(
        'consignor', 'consignee', 'destination'
    ).order_by('-cnote_id')

    # -------- Filters --------
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    status = request.GET.get('status')
    search = request.GET.get('search')

    if from_date:
        cnotes = cnotes.filter(date__gte=from_date)

    if to_date:
        cnotes = cnotes.filter(date__lte=to_date)

    if status:
        cnotes = cnotes.filter(status=status)

    if search:
        cnotes = cnotes.filter(
            Q(cnote_id__icontains=search) |
            Q(invoice_no__icontains=search)
        )

    # -------- Pagination --------
    paginator = Paginator(cnotes, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'status_choices': CnoteModel.STATUS_CHOICES,
        'filters': {
            'from_date': from_date,
            'to_date': to_date,
            'status': status,
            'search': search,
        }
    }

    return render(request, 'cnote_list.html', context)

def download_cnote_excel(request):
    qs = CnoteModel.objects.select_related(
        "consignor", "consignee", "destination"
    )
    from_date = request.GET.get("from_date")
    to_date = request.GET.get("to_date")
    status = request.GET.get("status")
    search = request.GET.get("search")
    if from_date:
        try:
            dt = datetime.strptime(from_date, "%Y-%m-%d")
            qs = qs.filter(date__gte=dt.date())
        except Exception as e:
            print("from_date error:", e)
    if to_date:
        try:
            dt = datetime.strptime(to_date, "%Y-%m-%d")
            qs = qs.filter(date__lte=dt.date())
        except Exception as e:
            print("to_date error:", e)
    if status:
        qs = qs.filter(status=status)

    if search and search.lower() != 'none':
        qs = qs.filter(
            Q(cnote_id__icontains=search) |
            Q(invoice_no__icontains=search)
        )
    else:
        if search:
            print("Search was 'None' or whitespace → skipped")
    wb = Workbook()
    ws = wb.active
    ws.title = "CNotes"

    headers = [
        "LR Date",
        "CNote No",
        "Operation Status",
        "Invoice No",
        "Consignor",
        "Consignee",
        "Destination",
        "Quantity",
        "Status"
    ]
    ws.append(headers)

    for c in qs:
        if c.status == "NEW":
            operation_status = "Booked"
        elif c.status == "DISPATCHED":
            operation_status = "Shipped"
        elif c.status == "DELIVERED":
            operation_status = "Delivered"
        else:
            operation_status = "-"

        ws.append([
            c.date.strftime("%d-%m-%Y"),
            c.cnote_id,
            operation_status,
            c.invoice_no or "",
            c.consignor.consignor_name,
            c.consignee.consignee_name,
            c.destination.location_name,
            c.total_item,
            c.get_status_display(),
        ])
    print("added")
    print(ws)
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    filename = f"CNotes_{datetime.now().strftime('%d%m%Y_%H%M%S')}.xlsx"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    wb.save(response)
    return response

def print_cnote(request, cnote_id):
    cnote = get_object_or_404(CnoteModel, cnote_id=cnote_id)
    
    context = {
        'cnote': cnote,
    }
    
    return render(request, 'cnotes/print_bill.html', context)