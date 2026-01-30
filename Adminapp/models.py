from django.db import models,transaction
from django.contrib.auth.models import AbstractUser
from django.db.models import Max
# Create your models here.

class Company(models.Model):
    comp_id=models.AutoField(primary_key=True)
    comp_name=models.CharField(max_length=200)
    comp_address=models.CharField(max_length=200)
    comp_phone = models.CharField(max_length=10)
    comp_email = models.EmailField()
    comp_gst = models.CharField(max_length=200,unique=True)
    comp_pan = models.CharField(max_length=200,unique=True)
    msme_no = models.CharField(max_length=200,unique=True)

    def save(self, *args, **kwargs):
        self.comp_name = (self.comp_name or '').upper().strip()
        self.comp_address = (self.comp_address or '').upper().strip()
        self.comp_gst = (self.comp_gst or '').upper().strip()
        self.comp_pan = (self.comp_pan or '').upper().strip()
        self.msme_no = (self.msme_no or '').upper().strip()
        
        super().save(*args, **kwargs)
    class Meta:
        db_table = 'company_table'
    def __str__(self):
        return self.comp_name
class Broker(models.Model):
    broker_id = models.AutoField(primary_key=True)
    broker_name = models.CharField(max_length=200)
    borker_shortname = models.CharField(max_length=200)
    broker_phone = models.CharField(max_length=200)
    booking_type = models.CharField(max_length=200)
    booking_address = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)
    document = models.FileField(upload_to='documents/', blank=True, null=True)
    def save(self, *args, **kwargs):
        self.broker_name = (self.broker_name or '').upper().strip()
        self.borker_shortname = (self.borker_shortname or '').upper().strip()  # note: typo in field name
        self.booking_type = (self.booking_type or '').upper().strip()
        self.booking_address = (self.booking_address or '').upper().strip()
        
        super().save(*args, **kwargs)
    class Meta:
        db_table = "broker_table"

    def __str__(self):
        return self.broker_name
    
class Branch(models.Model):
    branch_id = models.AutoField(primary_key=True)
    company = models.ForeignKey(Company,on_delete=models.CASCADE)
    branch_name = models.CharField(max_length=200)
    branch_code = models.PositiveIntegerField(
        blank=True,
        unique=True
    )
    branch_shortname = models.CharField(max_length=200)
    branch_type = models.CharField(max_length=200)
    branch_phone = models.CharField(max_length=10)
    branch_email = models.EmailField()
    broker = models.ForeignKey(Broker,on_delete=models.CASCADE)
    branch_address = models.CharField(max_length=200)
    services = models.CharField(max_length=200)
    category = models.CharField(max_length=10,null=True,blank=True)
    branch_is_active = models.BooleanField(default=True)
    def save(self, *args, **kwargs):
        self.branch_name = (self.branch_name or '').upper().strip()
        self.branch_code = (self.branch_code or '').upper().strip()
        self.branch_shortname = (self.branch_shortname or '').upper().strip()
        self.branch_type = (self.branch_type or '').upper().strip()
        self.branch_address = (self.branch_address or '').upper().strip()
        self.services = (self.services or '').upper().strip()
        self.category = (self.category or '').upper().strip() if self.category else None
        if not self.branch_code:
            with transaction.atomic():
                last_code = Branch.objects.aggregate(
                    max_code=Max('branch_code')
                )['max_code']

                self.branch_code = (last_code or 99) + 1
        super().save(*args, **kwargs)
    class Meta:
        db_table = "branch_table"
    def __str__(self):
        return self.branch_name
class State(models.Model):
    state_id = models.AutoField(primary_key=True)
    state_name = models.CharField(max_length=200)
    def save(self, *args, **kwargs):
        self.state_name = (self.state_name or '').upper().strip()
        super().save(*args, **kwargs)
    class Meta:
        db_table = "state_table"
    def __str__(self):
        return self.state_name
    
class District(models.Model):
    district_id = models.AutoField(primary_key=True)
    state = models.ForeignKey(State,on_delete=models.CASCADE)
    district_name = models.CharField(max_length=200)
    def save(self, *args, **kwargs):
        self.district_name = (self.district_name or '').upper().strip()
        super().save(*args, **kwargs)
    class Meta:
        db_table = "district_table"
    def __str__(self):
        return self.district_name
    

class Item(models.Model):
    item_id = models.AutoField(primary_key=True)
    item_name = models.CharField(max_length=200)
    item_is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=True)
    def save(self, *args, **kwargs):
        self.item_name = (self.item_name or '').upper().strip()
        super().save(*args, **kwargs)
    class Meta:
        db_table = "item_table"

    def __str__(self):
        return self.item_name
    
    
class Location(models.Model):
    location_id = models.AutoField(primary_key=True)
    district = models.CharField(max_length=200)
    state = models.CharField(max_length=200,null=True,blank=True)
    location_name = models.CharField(max_length=200)
    shortname = models.CharField(max_length=100, blank=True)
    pincode = models.CharField(max_length=20)
    company = models.ManyToManyField(Company)
    branch = models.ManyToManyField(Branch)
    def save(self, *args, **kwargs):
        self.district = (self.district or '').upper().strip()
        self.location_name = (self.location_name or '').upper().strip()
        if not self.shortname and self.location_name:
            self.shortname = self.generate_shortname()
        super().save(*args, **kwargs)
    def generate_shortname(self):
        name = (self.location_name or '').upper().strip()
        if not name:
            return ""
        name = name.replace('(PO)', '').replace('PO', '').replace('-', ' ').strip()

        words = name.split()

        if len(words) <= 1:
            return name[:3]

        result = words[0][0] + words[-1][:2]

        overrides = {
            'KOCHI': 'KCH',
            'ERNAKULAM': 'EKM',
            'FORTKOCHI': 'FTK',
            'FORT KOCHI': 'FTK',
            'MARADU': 'MRD',
            'KAKKANAD': 'KKD',
            'VYTTILA': 'VYT',
            'THOPPUMPADY': 'TPY',
        }

        for k, v in overrides.items():
            if k in name:
                return v

        return result.upper()[:3]
    class Meta:
        db_table = "location_table"
    def __str__(self):
        return self.location_name
    
class Vehicle(models.Model):
    vehicle_id = models.AutoField(primary_key=True)
    branch = models.ForeignKey(Branch,on_delete=models.CASCADE)
    registration_no = models.CharField(max_length=20)
    vehicle_is_active = models.BooleanField(default=True)
    vehicle_type = models.CharField(max_length=100)
    fuel_card = models.BooleanField(blank=True,null=True)
    fuel_type = models.CharField(max_length=30,blank=True,null=True)
    def save(self, *args, **kwargs):
        self.registration_no = (self.registration_no or '').upper().strip()
        self.vehicle_type = (self.vehicle_type or '').upper().strip()
        super().save(*args, **kwargs)
    class Meta:
        db_table = "vehicle_table"

class Driver(models.Model):
    driver_id= models.AutoField(primary_key=True)
    branch = models.ForeignKey(Branch,on_delete=models.CASCADE)
    driver_name=models.CharField(max_length=200)
    driver_phone=models.CharField(max_length=10)
    driver_address=models.CharField(max_length=200)
    driver_is_active=models.BooleanField(default=True)
    available_all=models.BooleanField(default=True)
    driver_document=models.FileField(upload_to='driver_documents', blank=True, null=True)
    def save(self, *args, **kwargs):
        self.driver_name = (self.driver_name or '').upper().strip()
        self.driver_address = (self.driver_address or '').upper().strip()
        super().save(*args, **kwargs)
    class Meta:
        db_table = "driver_table"
    def __str__(self):
        return self.driver_name
class Consignor(models.Model):
    consignor_id=models.AutoField(primary_key=True)
    consignor_code = models.PositiveIntegerField(unique=True,editable=False,verbose_name="Consignor Code",null=True)
    consignor_name=models.CharField(max_length=200)
    consignor_phone=models.CharField(max_length=200)
    gst_no=models.CharField(max_length=200)
    gst_type=models.CharField(max_length=200)
    address=models.CharField(max_length=200)
    billing_address=models.CharField(max_length=200)
    type=models.CharField(max_length=200)
    lr_charge=models.IntegerField()
    items = models.ManyToManyField(Item)
    state = models.ManyToManyField(Location)
    consignor_is_active=models.BooleanField(default=True)
    is_manual = models.BooleanField(default=True)
    pod_use = models.BooleanField(default=False)
    def save(self, *args, **kwargs):
        if not self.consignor_code: 
            with transaction.atomic():  
                max_code = Consignor.objects.aggregate(models.Max('consignor_code'))['consignor_code__max']
                next_code = (max_code or 999) + 1
                self.consignor_code = max(1000, next_code)
        self.consignor_name = (self.consignor_name or '').upper().strip()
        self.gst_no = (self.gst_no or '').upper().strip()
        self.gst_type = (self.gst_type or '').upper().strip()
        self.address = (self.address or '').upper().strip()
        self.billing_address = (self.billing_address or '').upper().strip()
        self.type = (self.type or '').upper().strip()
        super().save(*args, **kwargs)
    class Meta:
        db_table = "consignor_table"
    def __str__(self):
        return self.consignor_name
    
class Consignee(models.Model):
    consignee_id=models.AutoField(primary_key=True)
    consignee_name=models.CharField(max_length=200)
    consignee_phone=models.CharField(max_length=10)
    gst_no=models.CharField(max_length=200)
    consignee_address=models.CharField(max_length=200)
    consignee_is_active=models.BooleanField(default=True)
    def save(self, *args, **kwargs):
        self.consignee_name = (self.consignee_name or '').upper().strip()
        self.consignee_address = (self.consignee_address or '').upper().strip()
        super().save(*args, **kwargs)
    class Meta:
        db_table = "consignee_table"
    def __str__(self):
        return self.consignee_name
    
class UserModel(AbstractUser):
    branch=models.ForeignKey(Branch,on_delete=models.CASCADE,null=True,blank=True)
    role=models.CharField(max_length=20)
    phone = models.CharField(max_length=20,null=True,blank=True)
    def save(self, *args, **kwargs):
        self.role = (self.role or '').upper().strip()
        super().save(*args,**kwargs)

    class Meta:
        db_table="user_table"
    def __str__(self):
        return self.username
    

class Quotation(models.Model):
    quotation_id = models.AutoField(primary_key=True)
    agent = models.ForeignKey(Consignor, on_delete=models.CASCADE)
    location = models.ForeignKey(Location, on_delete=models.PROTECT)
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    rate = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        db_table = 'quotation_table'
        unique_together = [['agent', 'location', 'item']]