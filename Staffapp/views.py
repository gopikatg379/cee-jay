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
import json
import qrcode
import base64
import openpyxl
from django.db.models import F
from datetime import date
from io import BytesIO
from django.utils.dateparse import parse_date
from datetime import timedelta
from django.db.models.functions import TruncDate, Coalesce
from django.db.models import Sum, Count, IntegerField,DecimalField, Case, When
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

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
        branches = location.branch.all()
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
@login_required
def get_lr_charge(request):
    consignor_id = request.GET.get("consignor_id")
    lr_charge = 20

    consignor = Consignor.objects.filter(consignor_id=consignor_id).first()
    if consignor:
        if consignor.type == "PERMANENT":
            lr_charge = consignor.lr_charge or 20
        else:
            lr_charge = 20
    return JsonResponse({"lr_charge": lr_charge})
def calculate_commission(cnote):
    
    freight = cnote.freight
    lr_charge = float(cnote.lr_charge or 0)
    booking_branch = cnote.booking_branch
    delivery_branch = cnote.delivery_branch

    booking_obj = BookingCommission.objects.filter(
        branch=booking_branch,
        company=delivery_branch.company
    ).first()

    booking_amount = 0

    if booking_obj:
        freight_percent = booking_obj.percentage or 0
        lr_percent = booking_obj.lr_commission or 0 
        freight_commission = freight * freight_percent / 100
        lr_commission = lr_charge * lr_percent / 100
        booking_amount = freight_commission + lr_commission
        booking_amount = freight_commission + lr_commission
    delivery_obj = DeliveryCommission.objects.filter(
        branch=delivery_branch,
        company=cnote.delivery_branch.company,
        from_zone=booking_branch.category
    ).first()

    delivery_amount = 0

    if delivery_obj:

        deduction_percent = delivery_obj.deduction_percentage or 0
        deduction_amount = freight * deduction_percent / 100
        net_freight = freight - deduction_amount

        subtract_booking = False

        if booking_branch.category == "SOUTH":
            if delivery_branch.category == "NORTH":
                subtract_booking = True

        elif booking_branch.category == "NORTH":
            if delivery_branch.category == "SOUTH":
                subtract_booking = True

        if subtract_booking:
            base = net_freight - booking_amount
        else:
            base = net_freight
        normal_delivery = base * delivery_obj.percentage / 100

        rural_extra = 0
        if cnote.destination:
            rural_percent = cnote.destination.rural_commission_percentage or 0
            rural_extra = base * rural_percent / 100
        delivery_amount = normal_delivery + rural_extra

    return booking_amount, delivery_amount



@login_required
def get_commission_percentages(request):
    booking_branch_id = request.GET.get("booking_branch")
    delivery_branch_id = request.GET.get("delivery_branch")
    consignor_id = request.GET.get("consignor")
    location_id = request.GET.get('location')

    if not (booking_branch_id and delivery_branch_id and consignor_id):
        return JsonResponse({})

    consignor = Consignor.objects.filter(pk=consignor_id).first()
    booking_branch = Branch.objects.filter(pk=booking_branch_id).first()
    delivery_branch = Branch.objects.filter(pk=delivery_branch_id).first()
    location = Location.objects.filter(pk=location_id).first()

    if not consignor or not booking_branch or not delivery_branch:
        return JsonResponse({})


    booking_comm = BookingCommission.objects.filter(
        branch=booking_branch,
        company=delivery_branch.company
    ).first()

    delivery_comm = DeliveryCommission.objects.filter(
        branch=delivery_branch,
        company=delivery_branch.company,
        from_zone=booking_branch.category
    ).first()
    rural_percentage = 0
    if location.rural_commission_percentage:
        rural_percentage = location.rural_commission_percentage or 0
    return JsonResponse({
        "booking_percentage": booking_comm.percentage if booking_comm else 0,
        "lr_percentage": booking_comm.lr_commission if booking_comm else 0,
        "delivery_percentage": delivery_comm.percentage if delivery_comm else 0,
        "deduction_percentage": delivery_comm.deduction_percentage if delivery_comm else 0,
        "rural_percentage": rural_percentage,
    })

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
        branch = Branch.objects.filter(branch_id=user.branch_id).select_related("broker").first()
        if branch and branch.broker:
            allowed_payments = branch.broker.booking_type or []

    if user.role == 'ADMIN':
        branches = Branch.objects.all()
    else:
        branches = Branch.objects.filter(branch_id=user.branch_id)

    if request.method == "POST":
        data = request.POST
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
        obj.consignee_phone = data.get("receiver_phone")
        obj.user = user
        obj.eway_no = data.get('eway_no')
        consignor_id = data.get("consignor")
        consignor = Consignor.objects.filter(consignor_id=consignor_id).first()

        if consignor:
            if consignor.type == "TEMPORARY":
                obj.lr_charge = data.get("lr_charge")
            elif consignor.type == "PERMANENT":
                obj.lr_charge = consignor.lr_charge or 20
        else:
            obj.lr_charge = data.get("lr_charge")
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
        booking_comm, delivery_comm = calculate_commission(obj)

        obj.booking_commission_amount = booking_comm
        obj.delivery_commission_amount = delivery_comm

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
    return render(request, "cnotes/cnote_manage.html", context)


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
def get_consignee_phone(request):
    name = request.GET.get("name", "").upper().strip()
    try:
        consignee = Consignee.objects.get(consignee_name=name)
        return JsonResponse({"phone": consignee.consignee_phone})
    except Consignee.DoesNotExist:
        return JsonResponse({"phone": ""})
@csrf_exempt
def add_receiver_ajax(request):
    if request.method == "POST":
        data = json.loads(request.body)
        name = data.get("name", "").upper().strip()
        if not name:
            return JsonResponse({"success": False, "error": "Receiver name is required."})
        
        consignee = Consignee.objects.create(
            consignee_name=name,
            consignee_phone="",
            gst_no="",
            consignee_address="",
            consignee_is_active=True
        )
        return JsonResponse({"success": True, "id": consignee.consignee_id, "name": consignee.consignee_name})

    return JsonResponse({"success": False, "error": "Invalid request."})

@csrf_exempt
def add_shipper_ajax(request):
    if request.method == "POST":
        data = json.loads(request.body)

        name = data.get("name", "").strip()
        phone = data.get("phone", "").strip()

        if not name:
            return JsonResponse({"success": False, "error": "Name required"})

        consignor = Consignor.objects.create(
            consignor_name=name,
            consignor_phone=phone,
            type="TEMPORARY",
            lr_charge=0,
            gst_no="",
            gst_type="",
            address="",
            billing_address=""
        )

        default_items = Item.objects.filter(is_default=True)
        consignor.items.set(default_items)
        return JsonResponse({
            "success": True,
            "id": consignor.consignor_id,
            "name": consignor.consignor_name,
            "items": [
                {"item_id": i.item_id, "item_name": i.item_name, "rate": 0}
                for i in default_items
            ]
        })

    return JsonResponse({"success": False})

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

    return render(request, 'cnotes/cnote_list.html', context)

@login_required
def cnote_commission_view(request):
    today = timezone.now().date()
    user = request.user

    
    from_date = request.GET.get("from_date", "").strip()
    to_date = request.GET.get("to_date", "").strip()

    if from_date:
        from_date = parse_date(from_date)
    else:
        from_date = today - timedelta(days=30)

    if to_date:
        to_date = parse_date(to_date)
    else:
        to_date = today

    cnotes = CnoteModel.objects.select_related(
        "booking_branch",
        "delivery_branch"
    ).filter(
        date__range=(from_date, to_date)
    ).exclude(
        status="Cancelled"
    )
    if user.role == "ADMIN":
        branch_id = request.GET.get("branch", "").strip()
        branches = Branch.objects.filter(branch_is_active=True)

        if branch_id and branch_id != "all":
            cnotes = cnotes.filter(booking_branch_id=branch_id)

        branch_summary = (
            cnotes
            .values("booking_branch__branch_name","booking_branch_id")
            .annotate(

                paid_collection=Sum(
                    Case(
                        When(
                            Q(payment="PAID") &
                            Q(booking_branch_id=F("booking_branch_id")),
                            then=F("total")
                        ),
                        default=Value(0),
                        output_field=DecimalField()
                    )
                ),

                topay_collection=Sum(
                    Case(
                        When(
                            Q(payment="TOPAY") &
                            Q(delivery_branch_id=F("booking_branch_id")),
                            then=F("total")
                        ),
                        default=Value(0),
                        output_field=DecimalField()
                    )
                ),

                total_commission=Sum(
                    F("booking_commission_amount") +
                    F("delivery_commission_amount")
                )
            )
            .order_by("booking_branch__branch_name")
        )

        graph_labels = []
        collection_data = []
        commission_data = []

        for row in branch_summary:
            graph_labels.append(row["booking_branch__branch_name"])

            collection_total = (row["paid_collection"] or 0) + (row["topay_collection"] or 0)
            collection_data.append(float(collection_total))

            commission_data.append(float(row["total_commission"] or 0))

    else:
        branches = None 
        branch_id = None

        user_branch = user.branch

        cnotes = cnotes.filter(
            Q(booking_branch=user_branch) |
            Q(delivery_branch=user_branch)
        )
        date_summary = (
            cnotes
            .values("date")
            .annotate(

                paid_collection=Sum(
                    Case(
                        When(
                            Q(payment="PAID") &
                            Q(booking_branch_id=F("booking_branch_id")),
                            then=F("total")
                        ),
                        default=Value(0),
                        output_field=DecimalField()
                    )
                ),
                topay_collection=Sum(
                    Case(
                        When(
                            Q(payment="TOPAY") &
                            Q(delivery_branch_id=F("booking_branch_id")),
                            then=F("total")
                        ),
                        default=Value(0),
                        output_field=DecimalField()
                    )
                ),

                total_commission=Sum(
                    F("booking_commission_amount") +
                    F("delivery_commission_amount")
                )
            )
            .order_by("date")
        )

        graph_labels = []
        collection_data = []
        commission_data = []

        for row in date_summary:
            graph_labels.append(row["date"].strftime("%d-%m-%Y"))

            collection_total = (row["paid_collection"] or 0) + (row["topay_collection"] or 0)
            collection_data.append(float(collection_total))

            commission_data.append(float(row["total_commission"] or 0))
    cnotes = cnotes.order_by("-date")
    totals = cnotes.aggregate(
        total_qty=Sum("total_item"),
        total_freight=Sum("freight"),
        total_amount=Sum("total"),
        total_topay=Sum(
            Case(
                When(payment="TOPAY", then="freight"),
                default=Value(0),
                output_field=DecimalField()
            )
        ),

        total_paid=Sum(
            Case(
                When(payment="PAID", then="freight"),
                default=Value(0),
                output_field=DecimalField()
            )
        ),
        total_booking_commission=Sum("booking_commission_amount"),
        total_delivery_commission=Sum("delivery_commission_amount"),
    )
    paginator = Paginator(cnotes, 10)  
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    context = {
        "cnotes": page_obj,
        "page_obj": page_obj,
        "branches": branches,
        "branch_id": branch_id,
        "from_date": from_date,
        "to_date": to_date,
        "totals": totals,
        "graph_labels": graph_labels,
        "collection_data": collection_data,
        "commission_data": commission_data,
    }

    return render(request, "cnotes/cnote_commission.html", context)

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
        "LR Charge",
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
            c.lr_charge,
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
    qr = qrcode.make(cnote.cnote_number)
    buffer = BytesIO()
    qr.save(buffer, format="PNG")
    qr_base64 = base64.b64encode(buffer.getvalue()).decode()
    context = {
        'cnote': cnote,
        'qr_code': qr_base64
    }
    
    return render(request, 'cnotes/print_bill.html', context)

@require_POST
def cnote_cancel(request):
    cnote_id = request.POST.get("cnote_id")
    remark = request.POST.get("remark")

    cnote = get_object_or_404(CnoteModel, cnote_id=cnote_id)

    if cnote.status != CnoteModel.STATUS_CANCEL:
        cnote.status = CnoteModel.STATUS_CANCEL
        cnote.remarks = remark

        cnote.booking_commission_amount = 0
        cnote.delivery_commission_amount = 0
        cnote.save()

    return redirect('cnote_list')

def cnote_detail(request, pk):
    cnote = get_object_or_404(CnoteModel, pk=pk)
    trackings = cnote.trackings.all()
    context = {
        'cnote': cnote,
        'title': f'Basic Info - {cnote.cnote_number}',
        'trackings': trackings
    }
    return render(request, 'cnotes/cnote_detail.html', context)

@login_required
def receive_cnote(request, pk):
    cnote = get_object_or_404(CnoteModel, pk=pk)
    user_branch = request.user.branch
    cnote.manifest = None

    cnote.status = CnoteModel.STATUS_RECEIVED
    cnote.received_at = timezone.now()
    cnote.received_branch = user_branch
    cnote.received_by = request.user
    cnote.save()

    CnoteTracking.objects.create(
        cnote=cnote,
        branch=user_branch,
        status=CnoteModel.STATUS_RECEIVED,
        created_by=request.user
    )

    messages.success(request, "CNote received successfully.")
    return redirect("cnote_list")

@login_required
def manifest_manage(request):
    branch_users = UserModel.objects.filter(branch=request.user.branch)
    cnotes_qs = CnoteModel.objects.filter(
        status=CnoteModel.STATUS_RECEIVED,
        received_branch=request.user.branch,
        manifest__isnull=True
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
        branch = request.POST["booking_branch"]
        loaded_by = request.POST["loaded_by"]
        if not cnote_ids:
            messages.error(request, "Please select at least one CNote")
            return redirect(request.path)

        if manifest_type == "BRANCH" and not hub_branch_id:
            messages.error(request, "Please select Hub Branch")
            return redirect(request.path)
        try:
            with transaction.atomic():
                branch_obj = Branch.objects.select_for_update().get(branch_id=branch)
                last_manifest = ManifestModel.objects.filter(
                    from_branch=branch_obj
                ).order_by('-manifest_number').first()

                if last_manifest:
                    next_number = last_manifest.manifest_number + 1
                else:
                    next_number = 1000
                manifest = ManifestModel.objects.create(
                    manifest_number=next_number,
                    date=manifest_date,
                    driver_id=driver_id,
                    vehicle_id=vehicle_id,
                    from_branch = Branch.objects.get(branch_id=branch),
                    branch_id=hub_branch_id if manifest_type == "BRANCH" else None,
                    manifest_type=manifest_type,
                    loaded_by=UserModel.objects.get(id=loaded_by),
                    user=request.user
                )

                cnotes = CnoteModel.objects.select_for_update().filter(
                    cnote_id__in=cnote_ids,
                    manifest__isnull=True
                )
                if cnotes.count() != len(cnote_ids):
                    raise Exception("Some CNotes already manifested")

                if manifest_type == "BRANCH":
                    new_status = CnoteModel.STATUS_INTRANSIT 
                elif manifest_type == "DELIVERY":
                    new_status = CnoteModel.STATUS_DISPATCHED  
                else:
                    messages.error(request, "Invalid manifest type")
                    return redirect(request.path)
                for c in cnotes:
                    c.manifest = manifest
                    c.status = new_status
                    c.save()
                    CnoteTracking.objects.create(
                        cnote=c,
                        branch=manifest.branch,
                        status=new_status,
                        created_by=request.user
                    )

                messages.success(
                    request,
                    f"Manifest {manifest.manifest_id} created successfully"
                )
                return redirect("manifest_list")

        except Exception as e:
            messages.error(request, str(e))
            return redirect(request.path)

    context = {
        'page_obj': page_obj,
        'drivers': Driver.objects.all(),
        'branches': Branch.objects.all(),
        'vehicles': Vehicle.objects.all(),
        'branch_users':branch_users,
        'today': timezone.now().date()
    }

    return render(request, 'manifest/manifest_manage.html', context)

def manifest_list(request):

    manifest_type = request.GET.get(
        'manifest_type',
        ManifestModel.MANIFEST_DELIVERY
    )

    from_date = request.GET.get("from_date", "").strip()
    to_date = request.GET.get("to_date", "").strip()

    manifests = ManifestModel.objects.filter(
        manifest_type=manifest_type
    )
    if from_date:
        manifests = manifests.filter(date__gte=from_date)

    if to_date:
        manifests = manifests.filter(date__lte=to_date)

    manifests = manifests.order_by('-date',"-manifest_id")
    for m in manifests:
        m.can_update_delivery = m.cnotes.filter(
            status=CnoteModel.STATUS_DISPATCHED
        ).exists()
    paginator = Paginator(manifests, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'manifests': page_obj,
        'page_obj': page_obj,
        'selected_type': manifest_type,
        'filters': {
            'from_date': from_date,
            'to_date': to_date,
        }
    }

    return render(request, 'manifest/manifest_list.html', context)

@login_required
def manifest_edit(request, manifest_id):
    manifest = get_object_or_404(ManifestModel, pk=manifest_id)

    existing_cnotes = CnoteModel.objects.filter(manifest=manifest)

    available_cnotes = CnoteModel.objects.filter(
        status=CnoteModel.STATUS_RECEIVED,
        received_branch=request.user.branch,
        manifest__isnull=True
    ).order_by("-date")

    if request.method == "POST":

        remove_ids = request.POST.getlist("remove_cnotes[]")
        add_ids = request.POST.getlist("add_cnotes[]")

        manifest_date = request.POST.get("date")
        driver_id = request.POST.get("driver")
        vehicle_id = request.POST.get("vehicle")
        hub_branch_id = request.POST.get("hub_branch")

        try:
            with transaction.atomic():

                manifest.date = manifest_date
                manifest.driver_id = driver_id
                manifest.vehicle_id = vehicle_id

                if manifest.manifest_type == "BRANCH":
                    manifest.branch_id = hub_branch_id
                else:
                    manifest.branch = None

                manifest.save()

                for cid in remove_ids:
                    c = CnoteModel.objects.select_for_update().get(pk=cid)

                    if c.manifest_id != manifest.manifest_id:
                        continue

                    c.manifest = None
                    c.status = CnoteModel.STATUS_RECEIVED
                    c.save()

                    CnoteTracking.objects.create(
                        cnote=c,
                        branch=request.user.branch,
                        status=CnoteModel.STATUS_RECEIVED,
                        created_by=request.user
                    )

                for cid in add_ids:
                    c = CnoteModel.objects.select_for_update().get(pk=cid)

                    if c.manifest is not None:
                        continue

                    if manifest.manifest_type == "BRANCH":
                        new_status = CnoteModel.STATUS_INTRANSIT
                    else:
                        new_status = CnoteModel.STATUS_DISPATCHED

                    c.manifest = manifest
                    c.status = new_status
                    c.save()

                    CnoteTracking.objects.create(
                        cnote=c,
                        branch=request.user.branch,
                        status=new_status,
                        created_by=request.user
                    )

                messages.success(request, "Manifest updated successfully")
                return redirect("manifest_list")

        except Exception as e:
            messages.error(request, str(e))
            return redirect(request.path)

    context = {
        "manifest": manifest,
        "existing_cnotes": existing_cnotes,
        "available_cnotes": available_cnotes,
        "drivers": Driver.objects.all(),
        "vehicles": Vehicle.objects.all(),
        "branches": Branch.objects.all(),
        "today": timezone.now().date()
    }

    return render(request, "manifest/manifest_edit.html", context)

def print_manifest(request, manifest_id):
    manifest = get_object_or_404(ManifestModel, manifest_id=manifest_id)

    cnotes = CnoteModel.objects.filter(manifest=manifest)

    total_qty = cnotes.aggregate(
        Sum('total_item')
    )['total_item__sum'] or 0

    topay_cnotes = cnotes.filter(payment__iexact="TOPAY")

    total_to_pay = topay_cnotes.aggregate(
        Sum('total')
    )['total__sum'] or 0

    context = {
        'manifest': manifest,
        'cnotes': cnotes,
        'total_qty': total_qty,
        'total_to_pay': total_to_pay,
    }

    return render(request, 'manifest/print_manifest.html', context)

def manifest_drs_update(request, manifest_id):
    manifest = get_object_or_404(
        ManifestModel,
        manifest_id=manifest_id,
        manifest_type=ManifestModel.MANIFEST_DELIVERY
    )

    cnotes = CnoteModel.objects.filter(
        manifest=manifest,
        status=CnoteModel.STATUS_DISPATCHED 
    )

    total_topay = cnotes.filter(
        payment__iexact="TOPAY"
    ).aggregate(total=Sum("total"))["total"] or 0

    if request.method == "POST":
        with transaction.atomic():
            for c in cnotes:

                if f"return_{c.cnote_id}" in request.POST:
                    c.is_returned = True
                    c.status = CnoteModel.STATUS_RECEIVED
                    c.delivery_status = None
                    c.save()
                    CnoteTracking.objects.create(
                        cnote=c,
                        status="RETURNED",
                        branch=manifest.branch,
                        manifest=manifest,
                        created_by=request.user
                    )
                    continue

                delivery_status = request.POST.get(
                    f"status_{c.cnote_id}"
                )

                if not delivery_status:
                    continue

                c.delivery_status = delivery_status

                if delivery_status == "DELIVERED":
                    c.status = CnoteModel.STATUS_DELIVERED

                    if manifest.branch:
                        c.delivery_branch = manifest.branch
                    else:
                        print("WARNING: Manifest branch is None")

                    CnoteTracking.objects.create(
                        cnote=c,
                        status="DELIVERED",
                        branch=manifest.branch,
                        manifest=manifest,
                        created_by=request.user
                    )
                elif delivery_status in [
                    "TOPAY_RECEIVABLE",
                    "CREDIT_ALLOCATED"
                ]:
                    c.status = CnoteModel.STATUS_DELIVERED

                c.save()

        messages.success(request, "Delivery status updated successfully")
        return redirect("manifest_list")

    return render(
        request,
        "manifest/drs_update.html",
        {
            "manifest": manifest,
            "cnotes": cnotes,
            "total_topay": total_topay,
        }
    )

def booking_report(request):
    today = timezone.now().date()
    branches = Branch.objects.filter(branch_is_active=True)

    branch_id = request.GET.get("branch")
    from_date = request.GET.get("from_date")
    to_date = request.GET.get("to_date")
    if from_date:
        from_date = parse_date(from_date)
    else:
        from_date = today - timedelta(days=30)

    if to_date:
        to_date = parse_date(to_date)
    else:
        to_date = today

    cnotes = CnoteModel.objects.filter(
        date__range=(from_date, to_date)
    )

    if branch_id and branch_id != "all":
        cnotes = cnotes.filter(booking_branch_id=branch_id)

    paid = cnotes.filter(payment="PAID")
    paid_data = paid.aggregate(
        count=Count("cnote_id"),
        box_qty=Sum("total_item"),
        total_amount=Sum("total"),
        freight=Sum("freight"),
        lr_charge = Sum("lr_charge"),
        pickup_charge=Sum("pickup_charge"),
        hamali_charge=Sum("hamali_charge"),
        unloading_charge=Sum("unloading_charge"),
        door_delivery=Sum("door_delivery"),
        other_charge=Sum("other_charge")
    )
    topay = cnotes.filter(payment="TOPAY")

    topay_data = topay.aggregate(
        count=Count("cnote_id"),
        box_qty=Sum("total_item"),
        total_amount=Sum("total"),
        freight=Sum("freight"),
        lr_charge = Sum("lr_charge"),
        pickup_charge=Sum("pickup_charge"),
        hamali_charge=Sum("hamali_charge"),
        unloading_charge=Sum("unloading_charge"),
        door_delivery=Sum("door_delivery"),
        other_charge=Sum("other_charge")
    )

    credit = cnotes.filter(payment="CREDIT")

    credit_data = credit.aggregate(
        count=Count("cnote_id"),
        box_qty=Sum("total_item"),
        total_amount=Sum("total"),
        freight=Sum("freight"),
        lr_charge = Sum("lr_charge"),
        pickup_charge=Sum("pickup_charge"),
        hamali_charge=Sum("hamali_charge"),
        unloading_charge=Sum("unloading_charge"),
        door_delivery=Sum("door_delivery"),
        other_charge=Sum("other_charge")
    )
    gross_data = cnotes.aggregate(
        count=Count("cnote_id"),
        box_qty=Sum("total_item"),
        total_amount=Sum("total"),
        freight=Sum("freight"),
        lr_charge = Sum("lr_charge"),
        pickup_charge=Sum("pickup_charge"),
        hamali_charge=Sum("hamali_charge"),
        unloading_charge=Sum("unloading_charge"),
        door_delivery=Sum("door_delivery"),
        other_charge=Sum("other_charge"),
    )
    if gross_data["box_qty"]:
        gross_data["avg_box_rate"] = gross_data["freight"] // gross_data["box_qty"]
    else:
        gross_data["avg_box_rate"] = 0
    context = {
        "branches": branches,
        "branch_id": branch_id,
        "from_date": from_date,
        "to_date": to_date,

        "paid": paid_data,
        "topay": topay_data,
        "credit": credit_data,
        "gross": gross_data,
    }

    return render(request, "reports/booking_report.html", context)

def daily_booking_report(request):

    today = timezone.now().date()
    branches = Branch.objects.filter(branch_is_active=True)

    branch_id = request.GET.get("branch")
    from_date = request.GET.get("from_date")
    to_date = request.GET.get("to_date")

    if from_date:
        from_date = parse_date(from_date)
    else:
        from_date = today - timedelta(days=7)

    if to_date:
        to_date = parse_date(to_date)
    else:
        to_date = today

    if (to_date - from_date).days > 31:
        messages.error(request, "Maximum 31 days allowed.")
        to_date = from_date + timedelta(days=31)

    cnotes = CnoteModel.objects.filter(
        date__isnull=False,
        date__range=(from_date, to_date)
    )

    if branch_id and branch_id != "all":
        cnotes = cnotes.filter(booking_branch_id=branch_id)
    if (to_date - from_date).days > 31:
        messages.error(request, "Maximum 31 days allowed.")
        to_date = from_date + timedelta(days=31)
    daily_data = (
        cnotes
        .values("date")
        .annotate(
            count=Count("cnote_id"),
            box_qty=Coalesce(
                Sum("total_item"),
                Value(0, output_field=IntegerField())
            ),
            total_amount=Coalesce(
                Sum("total"),
                Value(0, output_field=DecimalField())
            ),
            paid=Coalesce(
                Sum(
                    Case(
                        When(payment="PAID", then="total"),
                        output_field=DecimalField()
                    )
                ),
                Value(0, output_field=DecimalField())
            ),

            topay=Coalesce(
                Sum(
                    Case(
                        When(payment="TOPAY", then="total"),
                        output_field=DecimalField()
                    )
                ),
                Value(0, output_field=DecimalField())
            ),

            credit=Coalesce(
                Sum(
                    Case(
                        When(payment="CREDIT", then="total"),
                        output_field=DecimalField()
                    )
                ),
                Value(0, output_field=DecimalField())
            ),
        )
        .order_by("date")
    )

    gross_data = cnotes.aggregate(
        count=Count("cnote_id"),
        box_qty=Coalesce(
            Sum("total_item"),
            Value(0, output_field=IntegerField())
        ),
        total_amount=Coalesce(
            Sum("total"),
            Value(0, output_field=DecimalField())
        ),
        paid=Coalesce(
            Sum(
                Case(
                    When(payment="PAID", then="total"),
                    output_field=DecimalField()
                )
            ),
            Value(0, output_field=DecimalField())
        ),

        topay=Coalesce(
            Sum(
                Case(
                    When(payment="TOPAY", then="total"),
                    output_field=DecimalField()
                )
            ),
            Value(0, output_field=DecimalField())
        ),

        credit=Coalesce(
            Sum(
                Case(
                    When(payment="CREDIT", then="total"),
                    output_field=DecimalField()
                )
            ),
            Value(0, output_field=DecimalField())
        ),
    )


    context = {
        "branches": branches,
        "branch_id": branch_id,
        "from_date": from_date,
        "to_date": to_date,
        "daily_data": daily_data,
        "gross": gross_data,
    }

    return render(request, "reports/daily_booking_report.html", context)

def booking_data(request):

    bookings = CnoteModel.objects.all().order_by("-date")
    branch_id = request.GET.get("branch")
    consignor_id = request.GET.get("consignor")
    consignee_id = request.GET.get("consignee")
    payment_type = request.GET.get("payment_type")
    from_date = request.GET.get("from_date")
    to_date = request.GET.get("to_date")
    if not to_date:
        to_date = date.today().strftime("%Y-%m-%d")
    if branch_id and branch_id != "all":
        bookings = bookings.filter(booking_branch_id=branch_id)

    if consignor_id:
        bookings = bookings.filter(consignor_id=consignor_id)

    if consignee_id:
        bookings = bookings.filter(consignee_id=consignee_id)

    if payment_type and payment_type != "all":
        bookings = bookings.filter(payment=payment_type)

    if from_date and to_date:
        bookings = bookings.filter(date__range=[from_date, to_date])
    paginator = Paginator(bookings, 20)  
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    query_params = request.GET.copy()
    if "page" in query_params:
        query_params.pop("page")

    query_string = query_params.urlencode()
    context = {
        "bookings": page_obj,
        "page_obj": page_obj,
        "branches": Branch.objects.all(),
        "consignors": Consignor.objects.all(),
        "consignees": Consignee.objects.all(),
        "branch_id": branch_id,
        "payment_type": payment_type,
        "from_date": from_date,
        "to_date": to_date,
        "query_string": query_string,
    }

    return render(request, "reports/booking_data.html", context)

def booking_excel(request):

    bookings = CnoteModel.objects.all()

    branch_id = request.GET.get("branch")
    consignor_id = request.GET.get("consignor")
    consignee_id = request.GET.get("consignee")
    payment_type = request.GET.get("payment_type")
    from_date = request.GET.get("from_date")
    to_date = request.GET.get("to_date")

    if branch_id and branch_id != "all":
        bookings = bookings.filter(booking_branch_id=branch_id)

    if consignor_id:
        bookings = bookings.filter(consignor_id=consignor_id)

    if consignee_id:
        bookings = bookings.filter(consignee_id=consignee_id)

    if payment_type and payment_type != "all":
        bookings = bookings.filter(payment_type=payment_type)

    if from_date:
        bookings = bookings.filter(date__gte=from_date)

    if to_date:
        bookings = bookings.filter(date__lte=to_date)

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Booking Data"

    headers = [
        "Date", "LR No", "Status", "Invoice",
        "Shipper", "Receiver", "Destination",
        "Qty", "Payment", "Freight", "LR",
        "Pickup", "Hamali", "Unloading",
        "Door Delivery", "Other", "Total"
    ]

    sheet.append(headers)
    total_qty = 0
    total_freight = 0
    total_lr = 0
    total_pickup = 0
    total_hamali = 0
    total_unloading = 0
    total_door = 0
    total_other = 0
    grand_total = 0

    for b in bookings:
        total_qty += b.total_item or 0
        total_freight += b.freight or 0
        total_lr += b.lr_charge or 0
        total_pickup += b.pickup_charge or 0
        total_hamali += b.hamali_charge or 0
        total_unloading += b.unloading_charge or 0
        total_door += b.door_delivery or 0
        total_other += b.other_charge or 0
        grand_total += b.total or 0
        sheet.append([
            b.date.strftime("%d-%m-%Y"),
            b.cnote_number,
            b.status,
            b.invoice_no,
            b.consignor.consignor_name,
            b.consignee.consignee_name,
            str(b.destination) if b.destination else "",
            b.total_item,
            b.payment,
            b.freight,
            b.lr_charge,
            b.pickup_charge,
            b.hamali_charge,
            b.unloading_charge,
            b.door_delivery,
            b.other_charge,
            b.total,
        ])
    sheet.append([])
    sheet.append([
        "", "", "", "", "", "", "Grand Total",
        total_qty,
        "",
        total_freight,
        total_lr,
        total_pickup,
        total_hamali,
        total_unloading,
        total_door,
        total_other,
        grand_total,
    ])
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = "attachment; filename=booking_data.xlsx"

    workbook.save(response)
    return response

def branch_commission(request, branch_id):

    branch = get_object_or_404(Branch, pk=branch_id)
    companies = Company.objects.all()

    booking_commissions = BookingCommission.objects.filter(branch=branch)
    delivery_commissions = DeliveryCommission.objects.filter(branch=branch)
    booking_data = {}
    for bc in booking_commissions:
        booking_data[bc.company.comp_id] = {
            "percentage": bc.percentage,
            "lr": bc.lr_commission,
        }

    delivery_data = {}
    for dc in delivery_commissions:
        delivery_data[(dc.company.comp_id, dc.from_zone)] = dc.percentage

    if request.method == "POST":
        for company in companies:
            lr = request.POST.get(f"lr_{company.comp_id}")
            percentage = request.POST.get(f"booking_{company.comp_id}")
            if percentage or lr:
                BookingCommission.objects.update_or_create(
                    branch=branch,
                    company=company,
                    defaults={"percentage": percentage,"lr_commission": float(lr or 0),}
                )
            for zone in ["NORTH", "CENTRAL", "SOUTH"]:

                percentage = request.POST.get(
                    f"delivery_{company.comp_id}_{zone}"
                )
                deduction = request.POST.get(
                    f"deduction_{company.comp_id}_{zone}"
                )
                if percentage:
                    DeliveryCommission.objects.update_or_create(
                        branch=branch,
                        company=company,
                        from_zone=zone,
                        defaults={"percentage": percentage,"deduction_percentage": deduction or 0}
                    )

        return redirect("branch_manage")

    context = {
        "branch": branch,
        "companies": companies,
        "booking_data": booking_data,
        "delivery_data": delivery_data,
    }

    return render(request, "branch/branch_commission.html", context)

def branch_commission_view(request, branch_id):

    branch = get_object_or_404(Branch, pk=branch_id)

    booking_commissions = BookingCommission.objects.filter(
        branch=branch
    ).select_related("company")

    delivery_commissions = DeliveryCommission.objects.filter(
        branch=branch
    ).select_related("company")

    context = {
        "branch": branch,
        "booking_commissions": booking_commissions,
        "delivery_commissions": delivery_commissions,
    }

    return render(request, "branch/view_commission.html", context)


def booking_summary_view(request):
    today = timezone.now().date()
    yesterday = today - timedelta(days=30)

    from_date = request.GET.get("from_date")
    to_date = request.GET.get("to_date")


    if not from_date or not to_date:
        from_date = yesterday
        to_date = today
    else:
        from_date = datetime.strptime(from_date, "%Y-%m-%d").date()
        to_date = datetime.strptime(to_date, "%Y-%m-%d").date()
    cnotes = CnoteModel.objects.filter(
        date__range=[from_date, to_date]
    )
    summary = (
        cnotes
        .values("booking_branch__branch_name")
        .annotate(
            total_consignment=Count("cnote_id"),
            total_box_qty=Sum("total_item"),
            paid=Sum("total", filter=Q(payment="PAID")),
            credit=Sum("total", filter=Q(payment="CREDIT")),
            topay=Sum("total", filter=Q(payment="TOPAY")),
            total_amount=Sum("total"),
        )
        .order_by("booking_branch__branch_name")
    )

    gross_total = cnotes.aggregate(
        total_consignment=Count("cnote_id"),
        total_box_qty=Sum("total_item"),
        paid=Sum("total", filter=Q(payment="PAID")),
        credit=Sum("total", filter=Q(payment="CREDIT")),
        topay=Sum("total", filter=Q(payment="TOPAY")),
        total_amount=Sum("total"),
    )

    context = {
        "summary": summary,
        "gross": gross_total,
        "from_date": from_date,
        "to_date": to_date,
    }

    return render(request, "reports/booking_summary.html", context)

def booking_commission_report(request):
    today = timezone.now().date()
    user = request.user

    from_date = request.GET.get("from_date", "").strip()
    to_date = request.GET.get("to_date", "").strip()
    branch_id = request.GET.get("branch", "").strip()

    if from_date:
        from_date = parse_date(from_date)
    else:
        from_date = today - timedelta(days=30)

    if to_date:
        to_date = parse_date(to_date)
    else:
        to_date = today
    
    cnotes = CnoteModel.objects.select_related(
        "booking_branch",
        "delivery_branch"
    ).filter(
        date__range=(from_date, to_date)
    ) 
    if user.role == "ADMIN":
        branches = Branch.objects.filter(branch_is_active=True)
        if branch_id and branch_id != "all":
            cnotes = cnotes.filter(booking_branch_id=branch_id)
    else:
        branches = None
        branch_id = None
        cnotes = cnotes.filter(booking_branch=user.branch)
    date_summary = (
        cnotes
        .values('date', 'payment')  
        .annotate(total=Sum('total'))  
        .order_by('date')
    )
    dates = sorted(list(set(item['date'] for item in date_summary)))

    paid_data = []
    topay_data = []
    credit_data = []

    for d in dates:
        paid_total = 0
        topay_total = 0
        credit_total = 0

        for item in date_summary:
            if item['date'] == d:
                if item['payment'] == "PAID":
                    paid_total = item['total'] or 0
                elif item['payment'] == "TOPAY":
                    topay_total = item['total'] or 0
                elif item['payment'] == "CREDIT":
                    credit_total = item['total'] or 0

        paid_data.append(paid_total)
        topay_data.append(topay_total)
        credit_data.append(credit_total)
    cnotes = cnotes.order_by("-date")

    paginator = Paginator(cnotes, 10)
    page_obj = paginator.get_page(request.GET.get("page"))


    totals = cnotes.aggregate(
        total_commission=Sum("booking_commission_amount")
    )
    gross_total = cnotes.aggregate(
        total_consignment=Count("cnote_id"),
        total_box_qty=Sum("total_item"),
        paid=Sum("total", filter=Q(payment="PAID")),
        credit=Sum("total", filter=Q(payment="CREDIT")),
        topay=Sum("total", filter=Q(payment="TOPAY")),
        total_amount=Sum("total"),
    )
    context = {
        "cnotes": page_obj,
        "page_obj": page_obj,
        "branches": branches,
        "branch_id": branch_id,
        "from_date": from_date,
        "to_date": to_date,
        "totals": totals,
        "graph_dates": json.dumps(
            [d.strftime("%d-%m-%Y") for d in dates]
        ),
        "paid_data": json.dumps([float(x) for x in paid_data]),
        "topay_data": json.dumps([float(x) for x in topay_data]),
        "credit_data": json.dumps([float(x) for x in credit_data]),
        "gross": gross_total,
    }

    return render(request, "reports/booking_commission_report.html", context)

def delivery_commission_report(request):
    today = timezone.now().date()
    user = request.user

    from_date = request.GET.get("from_date", "").strip()
    to_date = request.GET.get("to_date", "").strip()
    branch_id = request.GET.get("branch", "").strip()

    if from_date:
        from_date = parse_date(from_date)
    else:
        from_date = today - timedelta(days=30)

    if to_date:
        to_date = parse_date(to_date)
    else:
        to_date = today

    cnotes = CnoteModel.objects.filter(
        date__range=(from_date, to_date)
    )

    if user.role == "ADMIN":
        branches = Branch.objects.filter(branch_is_active=True)
        if branch_id and branch_id != "all":
            cnotes = cnotes.filter(delivery_branch_id=branch_id)
    else:
        branches = None
        branch_id = None
        cnotes = cnotes.filter(delivery_branch=user.branch)
    date_summary = (
        cnotes
        .values('date', 'payment')  
        .annotate(total=Sum('total'))  
        .order_by('date')
    )
    dates = sorted(list(set(item['date'] for item in date_summary)))

    paid_data = []
    topay_data = []
    credit_data = []

    for d in dates:
        paid_total = 0
        topay_total = 0
        credit_total = 0

        for item in date_summary:
            if item['date'] == d:
                if item['payment'] == "PAID":
                    paid_total = item['total'] or 0
                elif item['payment'] == "TOPAY":
                    topay_total = item['total'] or 0
                elif item['payment'] == "CREDIT":
                    credit_total = item['total'] or 0

        paid_data.append(paid_total)
        topay_data.append(topay_total)
        credit_data.append(credit_total)
    cnotes = cnotes.order_by("-date")

    paginator = Paginator(cnotes, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    totals = cnotes.aggregate(
        total_commission=Sum("delivery_commission_amount")
    )
    gross_total = cnotes.aggregate(
        total_consignment=Count("cnote_id"),
        total_box_qty=Sum("total_item"),
        paid=Sum("total", filter=Q(payment="PAID")),
        credit=Sum("total", filter=Q(payment="CREDIT")),
        topay=Sum("total", filter=Q(payment="TOPAY")),
        total_amount=Sum("total"),
    )
    context = {
        "cnotes": page_obj,
        "page_obj": page_obj,
        "branches": branches,
        "branch_id": branch_id,
        "from_date": from_date,
        "to_date": to_date,
        "totals": totals,
        "graph_dates": json.dumps(
            [d.strftime("%d-%m-%Y") for d in dates]
        ),
        "paid_data": json.dumps([float(x) for x in paid_data]),
        "topay_data": json.dumps([float(x) for x in topay_data]),
        "credit_data": json.dumps([float(x) for x in credit_data]),
        "gross": gross_total,
    }

    return render(request, "reports/delivery_commission_report.html", context)