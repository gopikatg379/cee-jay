from django.shortcuts import render,redirect
from Adminapp.models import *
from .models import *
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.db.models import Q,Value
from django.core.paginator import Paginator
from openpyxl import Workbook
from datetime import datetime
from django.http import HttpResponse
from django.utils import timezone
from django.contrib import messages
from django.db.models.functions import Replace

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
def cnote_manage_view(request, pk=None):
    user = request.user

    cnote = None
    if pk:
        cnote = get_object_or_404(CnoteModel, pk=pk)

    consignors = Consignor.objects.all()
    consignees = Consignee.objects.all()
    locations = Location.objects.all()
    items = Item.objects.all()
    allowed_payments = []

    if user.role == "ADMIN":
        allowed_payments = ["TOPAY", "PAID", "CREDIT"]
    else:
        # staff user → branch → broker
        branch = Branch.objects.filter(branch_id=user.branch_id).select_related("broker").first()
        if branch and branch.broker:
            allowed_payments = branch.broker.booking_type or []

    if user.role == 'ADMIN':
        branches = Branch.objects.all()
    else:
        branches = Branch.objects.filter(branch_id=user.branch_id)

    if request.method == "POST":
        data = request.POST
        print(data)
        if cnote:
            obj = cnote          
        else:
            obj = CnoteModel()  

        obj.date = data.get("date")
        obj.reference_no = data.get("reference_no")
        obj.payment = data.get("payment")
        obj.consignor_id = data.get("consignor")
        obj.consignee_id = data.get("consignee")
        obj.booking_branch_id = data.get("booking_branch")
        obj.delivery_branch_id = data.get("branch")
        obj.destination_id = data.get("location")
        obj.delivery_type = data.get("delivery_type")

        obj.lr_charge = data.get("lr_charge") or 0
        obj.invoice_no = data.get("invoice_no")
        obj.invoice_amt = data.get("invoice_amt") or 0
        obj.pickup_charge = data.get("pickup_charge") or 0
        obj.hamali_charge = data.get("hamali_charge") or 0
        obj.unloading_charge = data.get("unloading_charge") or 0
        obj.door_delivery = data.get("door_delivery") or 0
        obj.other_charge = data.get("other_charge") or 0
        obj.remarks = data.get('remarks')
        
        if not cnote:
            obj.total_item = 0
            obj.freight = 0
            obj.total = 0
            obj.save()

        if cnote:
            obj.items.all().delete()

        qtys = data.getlist("qty[]")
        rates = data.getlist("rate[]")
        totals = data.getlist("total[]")
        item_ids = data.getlist("item[]")

        total_items = 0
        freight = 0

        for i, item_id in enumerate(item_ids):
            if not item_id:
                continue
            qty = int(qtys[i])
            rate = float(rates[i])
            total = float(totals[i])

            CnoteItem.objects.create(
                cnote=obj,
                item_id=item_id,
                qty=qty,
                rate=rate,
                total=total
            )
            total_items += qty
            freight += total

        obj.total_item = total_items
        obj.freight = freight
        obj.total = freight + float(obj.lr_charge) + float(obj.pickup_charge) + float(obj.hamali_charge) + float(obj.unloading_charge) + float(obj.door_delivery) + float(obj.other_charge)
        obj.save()

        return redirect("cnote_list")

    context = {
        "cnote": cnote,
        "consignors": consignors,
        "consignees": consignees,
        "branches": branches,
        "locations": locations,
        "items": items,
        "allowed_payments": allowed_payments,
        "is_edit": bool(cnote),
    }
    return render(request, "cnote_manage.html", context)


def get_quotation_rates(request, consignor_id, location_id):
    selected_location = Location.objects.get(location_id=location_id)

    quotations = Quotation.objects.filter(
        agent_id=consignor_id,
        location__district=selected_location.district 
    ).select_related('item')
    data = []
    for q in quotations:
        data.append({
            "item_id": q.item.item_id,
            "item_name": q.item.item_name,
            "rate": float(q.rate)
        })
    return JsonResponse(data, safe=False)

def cnote_list_view(request):

    cnotes = CnoteModel.objects.select_related(
        'consignor', 'consignee', 'destination'
    ).order_by('-cnote_id')

    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    status = request.GET.get('status')
    search = request.GET.get('search')
    if search:
        normalized_search = search.replace('-', '')
    if from_date:
        cnotes = cnotes.filter(date__gte=from_date)

    if to_date:
        cnotes = cnotes.filter(date__lte=to_date)

    if status:
        cnotes = cnotes.filter(status=status)

    if search:
        normalized_search = search.replace('-', '')

        cnotes = cnotes.annotate(
            cnote_no_nodash=Replace('cnote_number', Value('-'), Value(''))
        ).filter(
            Q(cnote_no_nodash__icontains=normalized_search) |
            Q(invoice_no__icontains=search)
        )
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
        "Status",
        "Booking Branch",
        "Delivery Branch",
        "Reference No",
        "Remarks",
        "Pickup Charge",
        "Hamali Charge",
        "Unloading Charge",
        "Door Delivery",
        "Other Charge"
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
            c.booking_branch.branch_name,
            c.delivery_branch.branch_name,
            c.reference_no,
            c.remarks,
            c.pickup_charge,
            c.hamali_charge,
            c.unloading_charge,
            c.door_delivery,
            c.other_charge
        ])
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

def cnote_delete(request,cnote_id):
    cnote = get_object_or_404(CnoteModel,cnote_id=cnote_id)
    cnote.delete()
    return redirect('cnote_list')

def cnote_detail(request, pk):
    cnote = get_object_or_404(CnoteModel, pk=pk)
    context = {
        'cnote': cnote,
        'title': f'Basic Info - {cnote.cnote_number}',
    }
    return render(request, 'cnotes/cnote_detail.html', context)

@login_required
def receive_cnote(request, pk):
    cnote = get_object_or_404(CnoteModel, pk=pk)
    user_branch = request.user.branch

    if cnote.status == CnoteModel.STATUS_RECEIVED and cnote.received_branch == user_branch:
        messages.warning(request, "This CNote is already received by your branch.")
        return redirect("cnote_manage")

    cnote.status = CnoteModel.STATUS_RECEIVED
    cnote.received_at = timezone.now()
    cnote.received_branch = user_branch
    cnote.received_by = request.user
    cnote.save()

    messages.success(request, "CNote received successfully.")
    return redirect("cnote_list")

def manifest_manage(request):

    cnotes_qs = CnoteModel.objects.filter(
        manifest__isnull=True,
        status='RECEIVED'
    ).order_by("-date")

    paginator = Paginator(cnotes_qs, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    if request.method == "POST":
        cnote_ids = request.POST.getlist("cnotes[]")
        driver_id = request.POST.get("driver")
        vehicle_id = request.POST.get("vehicle")
        manifest_date = request.POST.get("date")
        manifest_type = request.POST.get("manifest_type")
        hub_branch_id = request.POST.get("hub_branch")

        if not cnote_ids:
            messages.error(request, "Please select at least one CNote")
            return redirect(request.path)

        if manifest_type == "BRANCH" and not hub_branch_id:
            messages.error(request, "Please select Hub Branch")
            return redirect(request.path)

        try:
            with transaction.atomic():
                manifest = ManifestModel.objects.create(
                    date=manifest_date,
                    driver_id=driver_id,
                    vehicle_id=vehicle_id,
                    branch_id=hub_branch_id if manifest_type == "BRANCH" else None
                )

                cnotes = CnoteModel.objects.select_for_update().filter(
                    cnote_id__in=cnote_ids,
                    manifest__isnull=True
                )
                if cnotes.count() != len(cnote_ids):
                    raise Exception("Some CNotes already manifested")

                new_status = (
                    CnoteModel.STATUS_INTRANSIT
                    if manifest_type == "BRANCH"
                    else CnoteModel.STATUS_DISPATCHED
                )

                for c in cnotes:
                    c.manifest = manifest
                    c.status = new_status
                    if manifest_type == "BRANCH":
                        c.delivery_branch_id = hub_branch_id
                    c.save()

                messages.success(
                    request,
                    f"Manifest {manifest.manifest_id} created successfully"
                )
                return redirect("cnote_list")

        except Exception as e:
            messages.error(request, str(e))
            return redirect(request.path)

    context = {
        'page_obj': page_obj,
        'drivers': Driver.objects.all(),
        'branches': Branch.objects.all(),
        'vehicles': Vehicle.objects.all(),
        'today': timezone.now().date()
    }

    return render(request, 'manifest_manage.html', context)
