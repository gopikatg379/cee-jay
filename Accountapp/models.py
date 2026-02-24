from django.db import models,transaction
from Staffapp.models import CnoteModel
from Adminapp.models import Branch

class BillingConsignor(models.Model):
    billing_consignor_id = models.AutoField(primary_key=True)
    billing_consignor_name = models.CharField(max_length=200)
    billing_consignor_code = models.PositiveIntegerField(unique=True,editable=False,verbose_name="Consignor Code")
    billing_consignor_phone = models.CharField(max_length=12)
    billing_consignor_gst = models.CharField(max_length=50)
    billing_consignor_gsttype = models.CharField(max_length=50)
    billing_consingor_address = models.CharField(max_length=100)
    billing_consignor_type = models.CharField(max_length=30)
    billing_consignor_active = models.BooleanField(default=True)
    billing_payment = models.CharField(max_length=20,null=True)
    def save(self, *args, **kwargs):
        if not self.billing_consignor_code: 
            with transaction.atomic():  
                max_code = BillingConsignor.objects.aggregate(models.Max('billing_consignor_code'))['billing_consignor_code__max']
                next_code = (max_code or 999) + 1
                self.billing_consignor_code = max(1000, next_code)
        self.billing_consignor_name = (self.billing_consignor_name or '').upper().strip()
        self.billing_consignor_gst = (self.billing_consignor_gst or '').upper().strip()
        self.billing_consignor_gsttype = (self.billing_consignor_gsttype or '').upper().strip()
        self.billing_consingor_address = (self.billing_consingor_address or '').upper().strip()
        self.billing_consignor_type = (self.billing_consignor_type or '').upper().strip()
        super().save(*args, **kwargs)

    class Meta:
        db_table = "billing_consignor_table"
    def __str__(self):
        return self.billing_consignor_name
    

class BillingConsignee(models.Model):
    billing_consignee_id = models.AutoField(primary_key=True)
    billing_consignee_name = models.CharField(max_length=200)
    billing_consignee_phone = models.CharField(max_length=12,null=True)
    billing_consignee_address = models.CharField(max_length=50,null=True)
    billing_consignee_active = models.BooleanField(default=True)

    class Meta:
        db_table = "billing_consignee_table"
    def __str__(self):
        return self.billing_consignee_name       

class CourierModel(models.Model):
    courier_name = models.CharField(max_length=50)
    courier_active = models.BooleanField(default=True)

    class Meta:
        db_table = "courier_table"
class Invoice(models.Model):
    invoice_number = models.CharField(max_length=50, unique=True)
    invoice_date = models.DateField()
    customer = models.ForeignKey(
        BillingConsignor,
        on_delete=models.CASCADE
    )
    invoiced_by = models.CharField(max_length=20)
    def total_amount(self):
        shipment_total = sum(
            s.total_amount() for s in self.couriershipment_set.all()
        )

        billing_total = sum(
            b.total_amount() for b in self.cnotebilling_set.all()
        )

        return shipment_total + billing_total
    def __str__(self):
        return self.invoice_number

class CourierShipment(models.Model):
    ALLOCATE = "ALLOCATED"
    INV_PENDING = "INV PENDING"
    INV_INVOICED = "INVOICED"
    STATUS = [
        (ALLOCATE,"Allocated"),
        (INV_PENDING,"INV Pending"),
        (INV_INVOICED,"Invoiced")
    ]
    consignor = models.ForeignKey(BillingConsignor,to_field='billing_consignor_code', on_delete=models.CASCADE,null=True)
    consignee = models.ForeignKey(BillingConsignee,on_delete=models.CASCADE,null=True)
    cnote_number = models.CharField(max_length=50,null=True)
    branch = models.ForeignKey(Branch,on_delete=models.CASCADE,null=True)
    courier = models.ForeignKey(CourierModel,on_delete=models.CASCADE,null=True)
    booking_date = models.DateField(null=True)
    destination = models.CharField(max_length=200,null=True)
    qty = models.IntegerField(null=True)
    rate = models.IntegerField(null=True)
    particulars = models.CharField(max_length=100,null=True)
    actual_weight = models.DecimalField(max_digits=8, decimal_places=2,null=True)
    charged_weight = models.DecimalField(max_digits=8, decimal_places=2,null=True)
    freight = models.DecimalField(max_digits=10, decimal_places=2,null=True)
    lr_charge = models.DecimalField(max_digits=10, decimal_places=2,null=True)
    unloading_charge= models.DecimalField(max_digits=10, decimal_places=2,null=True)
    other_charge = models.DecimalField(max_digits=10, decimal_places=2,null=True)
    status = models.CharField(max_length=50,choices=STATUS,null=True)
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    def total_amount(self):
        return self.freight + self.lr_charge+self.unloading_charge+self.other_charge 


class CnoteBilling(models.Model):
    INV_PENDING = "INV PENDING"
    INV_INVOICED = "INVOICED"
    STATUS = [
        (INV_PENDING,"INV Pending"),
        (INV_INVOICED,"Invoiced")
    ]
    cnote = models.ForeignKey(CnoteModel,on_delete=models.CASCADE)
    consignor = models.ForeignKey(BillingConsignor,on_delete=models.CASCADE)
    particulars = models.CharField(max_length=50,null=True)
    inv_freight = models.IntegerField()
    inv_lr =  models.IntegerField()
    inv_unloading = models.IntegerField()
    inv_other = models.IntegerField()
    weight = models.IntegerField(null=True)
    status = models.CharField(max_length=50,choices=STATUS)
    invoice = models.ForeignKey(
    Invoice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    def total_amount(self):
        return self.inv_freight + self.inv_lr+self.inv_unloading+self.inv_other 
    
    class Meta:
        db_table = "cnote_billing"


