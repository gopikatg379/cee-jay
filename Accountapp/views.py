from django.shortcuts import render,redirect,get_object_or_404
import json
import openpyxl
from django.http import HttpResponse
from .models import *
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Exists, OuterRef

def accounts_dashboard(req):
    return render(req,"accounts/accounts_dashboard.html")

def billing_consignor_manage(req,billing_consignor_id=None):
    query = req.GET.get('q', '').strip()

    shippers = BillingConsignor.objects.filter(billing_consignor_active=True).order_by('-billing_consignor_id')

    if query:
        shippers = shippers.filter(
            Q(billing_consignor_name__icontains=query) |
            Q(billing_consignor_phone__icontains=query) |
            Q(billing_consignor_gst__icontains=query) |
            Q(billing_consingor_address__icontains=query)
        )
    instance = None
    mode = req.GET.get('mode', 'list')
    if billing_consignor_id:
        mode = 'edit'
        instance = get_object_or_404(BillingConsignor, billing_consignor_id=billing_consignor_id)
    if req.method == 'POST':
        con = instance if billing_consignor_id else BillingConsignor()

        con.billing_consignor_name = req.POST.get('consignor_name', '').strip()
        con.billing_consignor_phone = req.POST.get('consignor_phone', '').strip()
        con.billing_consignor_gst = req.POST.get('gst_no', '').strip()
        con.billing_consignor_gsttype = req.POST.get('gst_type', '').strip()
        con.billing_consingor_address = req.POST.get('address', '').strip()
        con.billing_consignor_type = req.POST.get('type', '').strip()
        con.billing_consignor_active = 'consignor_is_active' in req.POST

        con.save()

        return redirect('billing_shipper_manage')

    return render(req, 'accounts/billing_consignor_manage.html', {
        'shippers': shippers,
        'shipper': instance,
        'active_tab': mode,
        'is_edit': bool(billing_consignor_id),
        'search_query': query, 
    })

def billing_consignor_excel(req):
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Billing Shipper"
    headers = [
        "Shipper Code", "Shipper Name", "Phone", "GST No",
        "GST Type", "Address", "Type","Active"
    ]
    sheet.append(headers)

    shippers = BillingConsignor.objects.all()

    for shipper in shippers:

        sheet.append([
            shipper.billing_consignor_code or "",
            shipper.billing_consignor_name,
            shipper.billing_consignor_phone,
            shipper.billing_consignor_gst,
            shipper.billing_consignor_gsttype,
            shipper.billing_consingor_address,
            shipper.billing_consignor_type,
            "YES" if shipper.billing_consignor_active else "NO",
        ])

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=billing_shippers.xlsx'

    workbook.save(response)
    return response

def billing_consignor_delete(req,billing_consignor_id):
    con = get_object_or_404(BillingConsignor,billing_consignor_id=billing_consignor_id)
    con.billing_consignor_active = False
    con.save()
    return redirect('shipper_manage')

def billing_consignee_manage(req,billing_consignee_id=None):
    query = req.GET.get('q', '').strip()

    receiver = BillingConsignee.objects.filter(billing_consignee_active=True).order_by('-billing_consignee_id')

    if query:
        receiver = receiver.filter(
            Q(billing_consignee_name__icontains=query) |
            Q(billing_consignee_phone__icontains=query) 
        )
    instance = None
    mode = req.GET.get('mode', 'list')
    if billing_consignee_id:
        mode = 'edit'
        instance = get_object_or_404(BillingConsignee, billing_consignee_id=billing_consignee_id)
    if req.method == 'POST':
        con = instance if billing_consignee_id else BillingConsignee()

        con.billing_consignee_name = req.POST.get('consignee_name', '').strip()
        con.billing_consignee_phone = req.POST.get('consignee_phone', '').strip()
        con.billing_consignee_address = req.POST.get('address', '').strip()
        con.billing_consignee_active = 'consignee_is_active' in req.POST

        con.save()

        return redirect('billing_receiver_manage')

    return render(req, 'accounts/billing_consignee_manage.html', {
        'receivers': receiver,
        'receiver': instance,
        'active_tab': mode,
        'is_edit': bool(billing_consignee_id),
        'search_query': query, 
    })

def billing_consignee_delete(req,billing_consignee_id):
    con = get_object_or_404(BillingConsignee,billing_consignee_id=billing_consignee_id)
    con.billing_consignee_active = False
    con.save()
    return redirect('billing_receiver_manage')

def courier_manage(req,id=None):
    query = req.GET.get('q', '').strip()

    couriers = CourierModel.objects.filter(courier_active=True).order_by('-id')

    if query:
        couriers = couriers.filter(courier_name__icontains=query)
    instance = None
    mode = req.GET.get('mode', 'list')
    if id:
        mode = 'edit'
        instance = get_object_or_404(CourierModel, id=id)
    if req.method == 'POST':
        con = instance if id else CourierModel()

        con.courier_name = req.POST.get('courier_name', '').strip()
        con.courier_active = 'courier_is_active' in req.POST
        con.save()

        return redirect('courier_manage')

    return render(req, 'accounts/courier_manage.html', {
        'couriers': couriers,
        'courier': instance,
        'active_tab': mode,
        'is_edit': bool(id),
        'search_query': query, 
    })

def courier_delete(req,id):
    con = get_object_or_404(CourierModel,id=id)
    con.courier_active = False
    con.save()
    return redirect('courier_manage')


@login_required
def create_billing(request):

    branch = request.user.branch
    consignors = BillingConsignor.objects.all()
    consignees = BillingConsignee.objects.all()
    search = request.GET.get("search")

    billed_cnotes = CnoteBilling.objects.filter(
        cnote=OuterRef('pk')
    )

    cnotes = CnoteModel.objects.filter(
        booking_branch=branch
    ).annotate(
        is_billed=Exists(billed_cnotes)
    ).filter(
        is_billed=False
    )

    if search:
        numbers = [x.strip() for x in search.split(",") if x.strip()]
        cnotes = cnotes.filter(cnote_number__in=numbers)

    if request.method == "POST":

        consignor_id = request.POST.get("consignor")
        consignor = BillingConsignor.objects.get(billing_consignor_id=consignor_id)

        selected_ids = request.POST.getlist("selected")

        for cnote_id in selected_ids:

            inv_freight = request.POST.get(f"freight_{cnote_id}") or 0
            inv_lr = request.POST.get(f"lr_{cnote_id}") or 0
            inv_unloading = request.POST.get(f"unloading_{cnote_id}") or 0
            inv_other = request.POST.get(f"other_{cnote_id}") or 0
            payment = request.POST.get(f"payment_{cnote_id}") 

            cnote = CnoteModel.objects.get(cnote_id=cnote_id)

            CnoteBilling.objects.create(
                cnote=cnote,
                consignor=consignor,
                payment=payment,
                inv_freight=int(inv_freight),
                inv_lr=int(inv_lr),
                inv_unloading=int(inv_unloading),
                inv_other=int(inv_other),
                status=CnoteBilling.INV_PENDING
            )

        return redirect("create_billing")

    return render(request, "accounts/create_billing.html", {
        "cnotes": cnotes,
        "consignors": consignors,
        "consignees":consignees,
    })