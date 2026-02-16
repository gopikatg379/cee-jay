from django.shortcuts import render,redirect,get_object_or_404
from .models import *
from django.contrib.auth.hashers import make_password
from django.contrib import messages
from django.db.models import Min
from collections import defaultdict
import openpyxl
from django.http import HttpResponse
from django.contrib.auth import authenticate,login,logout
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Case, When, Value, DecimalField, F, Q
from Staffapp.models import *


@login_required(login_url='/')
def dashboard(request):
    user = request.user
    if user.role != "ADMIN":

        branch = user.branch

        cnotes = CnoteModel.objects.filter(
            Q(booking_branch=branch) |
            Q(delivery_branch=branch)
        ).exclude(
            status__iexact="cancelled"
        )

        commission_data = cnotes.aggregate(

            booking_commission=Sum(
                Case(
                    When(
                        booking_branch=branch,
                        then=F("booking_commission_amount")
                    ),
                    default=Value(0),
                    output_field=DecimalField()
                )
            ),

            delivery_commission=Sum(
                Case(
                    When(
                        delivery_branch=branch,
                        then=F("delivery_commission_amount")
                    ),
                    default=Value(0),
                    output_field=DecimalField()
                )
            )
        )

        total_commission = (
            (commission_data["booking_commission"] or 0) +
            (commission_data["delivery_commission"] or 0)
        )

        collection_data = cnotes.aggregate(

            paid_collection=Sum(
                Case(
                    When(
                        Q(payment="PAID") &
                        Q(booking_branch=branch),
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
                        Q(delivery_branch=branch),
                        then=F("total")
                    ),
                    default=Value(0),
                    output_field=DecimalField()
                )
            )
        )

        total_collection = (
            (collection_data["paid_collection"] or 0) +
            (collection_data["topay_collection"] or 0)
        )

        wallet_balance = total_commission - total_collection

    else:

        wallet_balance = 0
        total_commission = 0
        total_collection = 0

    context = {
        "wallet_balance": wallet_balance,
        "total_commission": total_commission,
        "total_collection": total_collection,
    }
    return render(request,'dashboard.html',context)

@login_required(login_url='/')
def broker_manage_view(request, broker_id=None):
    query = request.GET.get('q', '').strip()
    brokers = Broker.objects.all().order_by('-broker_id')
    if query:
        brokers = brokers.filter(
            Q(broker_name__icontains=query) |
            Q(borker_shortname__icontains=query)
        )
    mode = request.GET.get('mode', 'list')
    instance = None
    if broker_id:
        instance = get_object_or_404(Broker, broker_id=broker_id)
        mode = 'edit'
    
    if request.method == 'POST':
        broker_name = request.POST['broker_name']
        short_name = request.POST['short_name']
        phone = request.POST['phone']
        booking_type = request.POST.getlist('booking_type')
        address = request.POST['address']
        document_file = request.FILES.get('document')
        is_active     = 'is_active' in request.POST
        if broker_id:
            agent = instance
            agent.broker_name = broker_name
            agent.borker_shortname = short_name
            agent.broker_phone = phone
            agent.booking_type = booking_type
            agent.booking_address = address
            agent.is_active = is_active
            if document_file:
                agent.document = document_file
            agent.save()
            return redirect('broker_manage')
        else:
            agent = Broker(broker_name=broker_name,borker_shortname=short_name,broker_phone=phone,booking_type=booking_type,
                        booking_address=address,document=document_file,is_active= is_active, )
            agent.save()
            return redirect('broker_manage')
    context = {
        'brokers': brokers,
        'active_tab': mode,
        'broker': instance,         
        'is_edit': bool(broker_id),
        'search_query': query,
    }
    return render(request, 'brokers/manage.html', context)

@login_required(login_url='/')
def broker_delete(request,broker_id):
    agent = get_object_or_404(Broker,broker_id=broker_id)
    agent.delete()
    return redirect('broker_manage')

@login_required(login_url='/')
def company_manage_view(request, comp_id=None):
    query = request.GET.get('q', '').strip()
    company = Company.objects.all().order_by('-comp_id')
    if query:
        company = company.filter(
            Q(comp_name__icontains=query) |
            Q(comp_gst__icontains=query)
        )
    mode = request.GET.get('mode', 'list')
    instance = None
    if comp_id:
        instance = get_object_or_404(Company, comp_id=comp_id)
        mode = 'edit'
    
    if request.method == 'POST':
        comp_name = request.POST['comp_name']
        comp_address = request.POST['comp_address']
        phone = request.POST['phone']
        comp_email = request.POST['comp_email']
        comp_gst = request.POST['comp_gst']
        comp_pan = request.POST['comp_pan']
        msme_no = request.POST['msme_no']
        if comp_id:
            comp = instance
            comp.comp_name = comp_name
            comp.comp_address = comp_address
            comp.comp_phone = phone
            comp.comp_email = comp_email
            comp.comp_gst = comp_gst
            comp.comp_pan = comp_pan
            comp.msme_no = msme_no
            comp.save()
            return redirect('company_manage')
        else:
            comp = Company(comp_name=comp_name,comp_address=comp_address,comp_phone=phone,comp_email=comp_email,
                        comp_gst=comp_gst,comp_pan=comp_pan,msme_no= msme_no, )
            comp.save()
            return redirect('company_manage')
    context = {
        'company': company,
        'active_tab': mode,
        'companies': instance,         
        'is_edit': bool(comp_id),
        'search_query': query,
    }
    return render(request, 'company_manage.html', context)

@login_required(login_url='/')
def company_delete(request,comp_id):
    comp = get_object_or_404(Company,comp_id=comp_id)
    comp.delete()
    return redirect('company_manage')

@login_required(login_url='/')
def branch_manage_view(request, branch_id=None):
    user=request.user
    query = request.GET.get('q', '').strip()
    branch = Branch.objects.all().order_by('-branch_id')
    if query:
        branch = branch.filter(
            Q(branch_name__icontains=query) |
            Q(branch_shortname__icontains=query) |
            Q(branch_code__icontains=query) 
        )
    comp = Company.objects.all()
    broker = Broker.objects.all()
    mode = request.GET.get('mode', 'list')
    instance = None
    if branch_id:
        instance = get_object_or_404(Branch, branch_id=branch_id)
        mode = 'edit'
    
    if request.method == 'POST':
        print(request.POST)
        company_id = request.POST['company']
        company=Company.objects.get(comp_id=company_id)
        branch_name = request.POST['branch_name']
        branch_shortname=request.POST['branch_shortname']
        branch_type = request.POST['branch_type']
        branch_address = request.POST['branch_address']
        phone = request.POST['branch_phone']
        branch_email = request.POST['branch_email']
        broker_id = request.POST['agent']
        broker = Broker.objects.get(broker_id=broker_id)
        services = request.POST['services']
        category = request.POST['category']
        is_active = 'is_active' in request.POST
        if branch_id:
            branch = instance
            branch.company = company
            branch.branch_name = branch_name
            branch.branch_shortname = branch_shortname
            branch.branch_type = branch_type
            branch.branch_phone = phone
            branch.branch_email = branch_email
            branch.broker = broker
            branch.branch_address = branch_address
            branch.services = services
            branch.category = category
            branch.branch_is_active = is_active
            branch.save()
            return redirect('branch_manage')
        else:
            branch = Branch(company = company,branch_name = branch_name,branch_shortname = branch_shortname,
                            branch_type = branch_type,branch_phone = phone,branch_email = branch_email,broker = broker,branch_address = branch_address,
                            services = services,category = category,branch_is_active = is_active)
            print("statred to saving..")
            branch.save()
            print("saved")
            return redirect('branch_manage')
    context = {
        'user':user,
        'company':comp,
        'agents':broker,
        'branchs': branch,
        'active_tab': mode,
        'branch': instance,         
        'is_edit': bool(branch_id),
        'search_query': query,
    }
    return render(request, 'branch_manage.html', context)

@login_required(login_url='/')
def branch_delete(request,branch_id):
    comp = get_object_or_404(Branch,branch_id=branch_id)
    comp.delete()
    return redirect('branch_manage')

@login_required(login_url='/')
def state_manage_view(request,state_id=None):
    query = request.GET.get('q', '').strip()
    state = Location.objects.values('state').distinct()
    if query:
        state = state.filter(
            Q(state__icontains=query)
        )
    return render(request,'state_manage.html',{'state':state,'search_query': query})

@login_required(login_url='/')
def district_manage_view(request):
    query = request.GET.get('q', '').strip()
    district = Location.objects.values('district','state').distinct().order_by('state')
    if query:
        district = district.filter(
            Q(state__icontains=query)|
            Q(district__icontains=query)
        )
    return render(request,'district_manage.html',{'districts':district,'search_query': query,})
    
@login_required(login_url='/')
def location_manage_view(request,location_id=None):
    query = request.GET.get('q', '').strip()
    locations = Location.objects.all().order_by('-location_id')
    if query:
        locations = locations.filter(
            Q(location_name__icontains=query) |
            Q(shortname__icontains=query) |
            Q(district__icontains=query) 
        )
    
    companies = Company.objects.all()
    branches = Branch.objects.all()
    mode = request.GET.get('mode', 'list')
    instance = None
    if location_id:
        instance = get_object_or_404(Location, location_id=location_id)
        mode = 'edit'
    selected_branch_ids = set()
    if instance: 
        selected_branch_ids = set(instance.branch.values_list('branch_id', flat=True))
    if request.method == 'POST':
        district_name = request.POST['district_name']
        state = request.POST['state_name']
        pincode = request.POST['pincode']
        location_name = request.POST['location_name']
        rural_percentage = request.POST['rural_commission_percentage']
        shortname = request.POST.get('shortname', '').strip().upper()
        branches_data = {
            key.replace('branches[', '').replace(']', ''): value
            for key, value in request.POST.items()
            if key.startswith('branches[') and value
        }
        if instance:
            loc = instance
        else:
            loc = Location()
        loc.district = district_name
        loc.state=state
        loc.pincode = pincode
        loc.location_name = location_name
        loc.shortname = shortname
        loc.rural_commission_percentage = rural_percentage
        loc.save()
        loc.company.clear()
        loc.branch.clear()
        for comp_id, branch_id in branches_data.items():
            company = Company.objects.get(comp_id=comp_id)
            branch = Branch.objects.get(branch_id=branch_id)
            loc.company.add(company)
            loc.branch.add(branch)
        return redirect('location_manage')
    context = {
        'companies':companies,
        'branches':branches,
        'locations':locations,
        'location':instance,
        'active_tab': mode,
        'is_edit': bool(location_id),
        'selected_branch_ids': selected_branch_ids,
        'search_query': query,
    }
    return render(request,'location_manage.html',context)

@login_required(login_url='/')
def location_delete(request,location_id):
    loc = get_object_or_404(Location,location_id=location_id)
    loc.delete()
    return redirect('location_manage')

@login_required(login_url='/')
def item_manage_view(request,item_id=None):
    query = request.GET.get('q', '').strip()
    item = Item.objects.all().order_by('-item_id')
    if query:
        item = item.filter(
            Q(item_name__icontains=query)
        )
    mode = request.GET.get('mode', 'list')
    instance = None
    if item_id:
        instance = get_object_or_404(Item, item_id=item_id)
        mode = 'edit'
    if request.method == 'POST':
        item_name = request.POST['item_name']
        is_active = 'is_active' in request.POST
        is_default = 'is_default' in request.POST
        if item_id:
            item = instance
            item.item_name=item_name
            item.item_is_active=is_active
            item.is_default=is_default
            item.save()
            return redirect('item_manage')
        else:
            item = Item(item_name=item_name,item_is_active=is_active,is_default=is_default)
            item.save()
            return redirect('item_manage')
    context = {
        'item':item,
        'items':instance,
        'active_tab': mode,
        'is_edit': bool(item_id),
        'search_query': query,
    }
    return render(request,'item_manage.html',context)

@login_required(login_url='/')
def item_delete(request,item_id):
    ite = get_object_or_404(Item,item_id=item_id)
    ite.delete()
    return redirect('item_manage')


@login_required(login_url='/')
def vehicle_manage_view(request,vehicle_id=None):
    query = request.GET.get('q', '').strip()
    vehicle = Vehicle.objects.all().order_by('-vehicle_id')
    if query:
        vehicle = vehicle.filter(
            Q(registration_no__icontains=query)
        )
    all_branches = Branch.objects.all()
    mode = request.GET.get('mode', 'list')
    instance = None
    if vehicle_id:
        instance = get_object_or_404(Vehicle, vehicle_id=vehicle_id)
        mode = 'edit'
    if request.method == 'POST':
        branch_id = request.POST['branch']
        branch = Branch.objects.get(branch_id=branch_id)
        registration_no = request.POST['registration_no']
        vehicle_type=request.POST['vehicle_type']
        is_active = 'is_active' in request.POST
        fuel_card = 'fuel_card' in request.POST
        fuel_type=request.POST['fuel_type']
        duplicate_check = Vehicle.objects.filter(
            registration_no=registration_no
        )
        if vehicle_id:
            duplicate_check = duplicate_check.exclude(vehicle_id=vehicle_id)
        if duplicate_check.exists():
            messages.error(
                request,
                f"Registration number <strong>{registration_no}</strong> already exists!",
                extra_tags='danger'
            )   
            context = {
                'vehicle': vehicle,
                'branches': all_branches,
                'vehicles': instance or Vehicle(
                    branch=branch,
                    registration_no=registration_no,
                    vehicle_type=vehicle_type,
                    vehicle_is_active=is_active,
                    fuel_card=fuel_card,
                    fuel_type=fuel_type
                ),
                'active_tab': 'add' if not vehicle_id else 'edit',
                'is_edit': bool(vehicle_id),
                'form_data': request.POST,
            }
            return render(request, 'vehicle_manage.html', context)
        if vehicle_id:
            vle = instance
            vle.branch=branch
            vle.registration_no=registration_no
            vle.vehicle_is_active=is_active
            vle.vehicle_type=vehicle_type
            vle.fuel_type=fuel_type
            vle.fuel_card=fuel_card
            vle.save()
            return redirect('vehicle_manage')
        else:
            vle = Vehicle(branch=branch,registration_no=registration_no,vehicle_is_active=is_active,vehicle_type=vehicle_type,fuel_card=fuel_card,fuel_type=fuel_type)
            vle.save()
            messages.success(request, "Vehicle saved successfully!")
            return redirect('vehicle_manage')
    context = {
        'vehicle':vehicle,
        'branches':all_branches,
        'vehicles':instance,
        'active_tab': mode,
        'is_edit': bool(vehicle_id),
        'search_query': query,
    }
    return render(request,'vehicle_manage.html',context)

@login_required(login_url='/')
def vehicle_delete(request,vehicle_id):
    vle = get_object_or_404(Vehicle,vehicle_id=vehicle_id)
    vle.delete()
    return redirect('vehicle_manage')

@login_required(login_url='/')
def user_manage_view(request, id=None):
    query = request.GET.get('q', '').strip()
    users = UserModel.objects.all().order_by('-id')
    if query:
        users = users.filter(
            Q(username__icontains=query)|
            Q(role__icontains=query)
        )
    branches = Branch.objects.all()
    mode = request.GET.get('mode', 'list')
    instance = None

    if id:
        instance = get_object_or_404(UserModel, id=id)
        mode = 'edit'

    if request.method == 'POST':
        branch_id = request.POST.get('branch')
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        role = request.POST.get('role')
        is_active = 'is_active' in request.POST

        try:
            branch = Branch.objects.get(branch_id=branch_id)
        except Branch.DoesNotExist:
            messages.error(request, "Selected branch does not exist!")
            branch = None

        duplicate = UserModel.objects.filter(username=username)
        if id:
            duplicate = duplicate.exclude(id=id)

        if duplicate.exists():
            messages.error(request, f"Username <strong>{username}</strong> already exists!")
            context = {
                'user': users,
                'branches': branches,
                'users': instance or UserModel(
                    branch=branch,
                    username=username,
                    email=email,
                    phone=phone,
                    role=role,
                    is_active=is_active
                ),
                'active_tab': 'edit' if id else 'add',
                'is_edit': bool(id),
            }
            return render(request, 'user_manage.html', context)

    
        if id:
            user = instance
        else:
            user = UserModel()

        user.branch = branch
        user.username = username
        user.email = email
        user.phone = phone  
        user.role = role
        user.is_active = is_active

        
        if not id:  
            user.set_password(username.lower() + '123')  
            user.save()  

            
            password = f"{username.lower()}{str(user.id).zfill(4)}"
            user.set_password(password)
            user.save(update_fields=['password'])  

            messages.success(
                request,
                f"User created successfully! Password: <strong>{password}</strong>"
            )
        else:
            password = f"{username.lower()}{str(user.id).zfill(4)}"
            user.set_password(password)
            user.save()
            messages.info(request, f"User updated. Password reset to: {password}")

        return redirect('user_manage')

    context = {
        'user_list': users,
        'branches': branches,
        'users': instance,
        'active_tab': mode,
        'is_edit': bool(id),
        'search_query': query,
    }
    return render(request, 'user_manage.html', context)

@login_required(login_url='/')
def user_delete(request,id):
    ur = get_object_or_404(UserModel,id=id)
    ur.delete()
    return redirect('user_manage')

@login_required(login_url='/')
def driver_manage_view(request, driver_id=None):
    query = request.GET.get('q', '').strip()
    driver = Driver.objects.all().order_by('-driver_id')
    if query:
        driver = driver.filter(
            Q(driver_name__icontains=query)
        )
    branches = Branch.objects.all()
    mode = request.GET.get('mode', 'list')
    instance = None

    if driver_id:
        instance = get_object_or_404(Driver, driver_id=driver_id)
        mode = 'edit'

    if request.method == 'POST':
        branch_id = request.POST.get('branch')
        driver_name = request.POST.get('driver_name', '').strip()
        driver_address = request.POST.get('driver_address', '').strip()
        driver_phone = request.POST.get('phone', '').strip()
        available_all = 'available_all' in request.POST
        driver_is_active = 'is_active' in request.POST
        driver_document=request.FILES.get('driver_document')
        try:
            branch = Branch.objects.get(branch_id=branch_id)
        except Branch.DoesNotExist:
            messages.error(request, "Selected branch does not exist!")
            branch = None

        if driver_id:
            drv = instance
            drv.branch=branch
            drv.driver_name=driver_name
            drv.driver_address=driver_address
            drv.driver_phone=driver_phone
            drv.driver_document=driver_document
            drv.driver_is_active=driver_is_active
            drv.available_all=available_all
            drv.save()
            return redirect('driver_manage')
        else:
            drv = Driver(branch=branch,driver_name=driver_name,driver_phone=driver_phone,driver_address=driver_address,driver_document=driver_document,
                          driver_is_active=driver_is_active,available_all=available_all)
            drv.save()
            return redirect('driver_manage')
    context = {
        'driver':driver,
        'branches':branches,
        'drivers':instance,
        'active_tab': mode,
        'is_edit': bool(driver_id),
        'search_query': query,
    }
    return render(request, 'driver_manage.html', context)
@login_required(login_url='/')
def driver_delete(request,driver_id):
    drv = get_object_or_404(Driver,driver_id=driver_id)
    drv.delete()
    return redirect('driver_manage')

@login_required(login_url='/')
def shipper_manage_view(request, consignor_id=None):
    query = request.GET.get('q', '').strip()

    shippers = Consignor.objects.all().order_by('-consignor_id')

    if query:
        shippers = shippers.filter(
            Q(consignor_name__icontains=query) |
            Q(consignor_phone__icontains=query) |
            Q(gst_no__icontains=query) |
            Q(address__icontains=query)
        )

    items = Item.objects.all()

    states = (
        Location.objects
        .filter(state__isnull=False)
        .exclude(state='')
        .order_by('state')
    )
    unique_states = []
    seen = set()

    for loc in states:
        if loc.state not in seen:
            seen.add(loc.state)
            unique_states.append(loc)
    instance = None
    mode = request.GET.get('mode', 'list')
    if consignor_id:
        mode = 'edit'
        instance = get_object_or_404(Consignor, consignor_id=consignor_id)
    if request.method == 'POST':
        selected_item_ids = request.POST.getlist('items')
        selected_state_ids = [int(sid) for sid in request.POST.getlist('states') if sid.strip().isdigit()]

        con = instance if consignor_id else Consignor()

        con.consignor_name = request.POST.get('consignor_name', '').strip()
        con.consignor_phone = request.POST.get('consignor_phone', '').strip()
        con.gst_no = request.POST.get('gst_no', '').strip()
        con.gst_type = request.POST.get('gst_type', '').strip()
        con.address = request.POST.get('address', '').strip()
        con.billing_address = request.POST.get('billing_address', '').strip()
        con.type = request.POST.get('type', '').strip()
        con.lr_charge = request.POST.get('lr_charge') or 0
        con.consignor_is_active = 'consignor_is_active' in request.POST
        con.is_manual = 'is_manual' in request.POST
        con.pod_use = 'pod_use' in request.POST

        con.save()
        con.items.set(selected_item_ids)
        con.state.set(selected_state_ids)

        return redirect('shipper_manage')

    return render(request, 'shipper_manage.html', {
        'items': items,
        'states': unique_states,
        'shippers': shippers,
        'shipper': instance,
        'active_tab': mode,
        'is_edit': bool(consignor_id),
        'search_query': query,
    })

@login_required(login_url='/')
def shipper_delete(request,consignor_id):
    con = get_object_or_404(Consignor,consignor_id=consignor_id)
    con.delete()
    return redirect('shipper_manage')
@login_required(login_url='/')
def receiver_manage_view(request, consignee_id=None):
    query = request.GET.get('q', '').strip()
    receiver = Consignee.objects.all().order_by('-consignee_id')
    if query:
        receiver = receiver.filter(
            Q(consignee_name__icontains=query)|
            Q(gst_no__icontains=query)
        )
    mode = request.GET.get('mode', 'list')
    instance = None

    if consignee_id:
        instance = get_object_or_404(Consignee, consignee_id=consignee_id)
        mode = 'edit'

    if request.method == 'POST':
        consignee_name = request.POST.get('consignee_name', '').strip()
        consignee_phone = request.POST.get('consignee_phone', '').strip()
        gst_no = request.POST.get('gst_no', '').strip()
        consignee_address = request.POST.get('consignee_address', '').strip()
        consignee_is_active = 'consignee_is_active' in request.POST

        if consignee_id:
            con = instance
            con.consignee_name=consignee_name
            con.consignee_phone=consignee_phone
            con.gst_no=gst_no
            con.consignee_address=consignee_address
            con.consignee_is_active=consignee_is_active
            con.save()
            return redirect('receiver_manage')
        else:
            con = Consignee(consignee_name=consignee_name,gst_no=gst_no,consignee_address=consignee_address,
                          consignee_phone=consignee_phone,consignee_is_active=consignee_is_active)
            con.save()
            return redirect('receiver_manage')
    context = {
        'receiver':receiver,
        'receivers':instance,
        'active_tab': mode,
        'is_edit': bool(consignee_id),
        'search_query': query,
    }
    return render(request, 'receiver_manage.html', context)
@login_required(login_url='/')
def receiver_delete(request,consignee_id):
    con = get_object_or_404(Consignee,consignee_id=consignee_id)
    con.delete()
    return redirect('receiver_manage')

@login_required(login_url='/')
def user_reset_password(request, user_id):
    user = get_object_or_404(UserModel, id=user_id)

    if request.method == 'POST':
        new_password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        if new_password != confirm_password:
            messages.error(request, "Passwords do not match")
            return redirect('user_reset_password', user_id=user.id)

        user.password = make_password(new_password)
        user.save()

        messages.success(request, f"Password reset successfully for {user.username} Password reset to: {new_password}")
        return redirect('user_manage')

    return render(request, 'reset_password.html', {
        'user_obj': user
    })


@login_required(login_url='/')
def consignor_quotation(request, consignor_id):
    consignor = get_object_or_404(Consignor, consignor_id=consignor_id)

    if request.method == "POST":
        saved_count = 0

        with transaction.atomic():
            for key, value in request.POST.items():
                if not key.startswith("rate__"):
                    continue
                print(f"Processing: {key} = {value}")
                try:
                    _, loc_id_str, item_id_str = key.split("__")
                    location_id = int(loc_id_str)
                    item_id = int(item_id_str)

                    rate_str = value.strip()
                    if not rate_str:
                        continue

                    rate = float(rate_str)
                    if rate < 0:
                        continue 
                    print(rate)
                    location = Location.objects.get(location_id=location_id)
                    item = Item.objects.get(item_id=item_id)

                    Quotation.objects.update_or_create(
                        agent=consignor,
                        location=location,
                        item=item,
                        defaults={"rate": rate}
                    )

                    saved_count += 1

                except Exception as e:
                    print(f"ERROR on {key} = {value} → {type(e).__name__}: {str(e)}")
                    continue 

        if saved_count > 0:
            messages.success(request, f"Saved {saved_count} rate(s) successfully.")
        else:
            messages.warning(request, "No valid rates were entered.")

        return redirect("shipper_quotation", consignor_id=consignor_id)
    selected_locs = consignor.state.all()
    operated_states = selected_locs.values_list("state", flat=True).distinct()
    existing_rates = {}
    quotations = Quotation.objects.filter(agent=consignor)
    for q in quotations:
        key = f"{q.location.location_id}_{q.item.item_id}"
        existing_rates[key] = float(q.rate)

    all_districts_by_state = defaultdict(list)

    for state_name in operated_states:
        if not state_name:
            continue

        qs = Location.objects.filter(state=state_name).order_by("district")

        seen_districts = set()
        unique_objs = []

        for loc in qs:
            district_normalized = (loc.district or "").strip().title()
            if district_normalized and district_normalized not in seen_districts:
                seen_districts.add(district_normalized)
                unique_objs.append(loc)

        if unique_objs:
            all_districts_by_state[state_name] = unique_objs
    
    context = {
        "shipper": consignor,
        "all_districts_by_state": dict(all_districts_by_state),
        "existing_rates": existing_rates,
    }

    return render(request, "shipper_quotation.html", context)

@login_required(login_url='/')
def shipper_export_excel(request):
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Shippers"
    headers = [
        "Shipper Code", "Shipper Name", "Phone", "GST No",
        "GST Type", "Address", "Billing Address",
        "LR Charge", "Type", "Items", "States",
        "Active", "Manual", "POD"
    ]
    sheet.append(headers)

    shippers = Consignor.objects.all()

    for shipper in shippers:
        items = ", ".join([i.item_name for i in shipper.items.all()])
        states = ", ".join([s.state for s in shipper.state.all()])

        sheet.append([
            shipper.consignor_code or "",
            shipper.consignor_name,
            shipper.consignor_phone,
            shipper.gst_no,
            shipper.gst_type,
            shipper.address,
            shipper.billing_address,
            shipper.lr_charge,
            shipper.type,
            items,
            states,
            "YES" if shipper.consignor_is_active else "NO",
            "YES" if shipper.is_manual else "NO",
            "YES" if shipper.pod_use else "NO",
        ])

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=shippers.xlsx'

    workbook.save(response)
    return response

def login_manage_view(request):
    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(username=username,password=password)
        if user:
            login(request,user)
            return redirect('dashboard')
        else:
            messages.error(request,"Invalid Credentials")
            return redirect('/')
    return render(request,'login.html')

def logout_view(request):
    logout(request)
    return redirect('login_manage')