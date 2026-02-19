from django.db import models,transaction
from Staffapp.models import CnoteModel

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
    billing_consignee_phone = models.CharField(max_length=12)
    billing_consignee_address = models.CharField(max_length=50)
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


class CourierShipment(models.Model):
    consignor = models.ForeignKey(BillingConsignor,to_field='billing_consignor_code', on_delete=models.CASCADE)
    consignee = models.ForeignKey(BillingConsignee,on_delete=models.CASCADE,null=True)
    booking_date = models.DateField()
    destination = models.CharField(max_length=200)
    qty = models.IntegerField()
    rate = models.IntegerField()
    particulars = models.CharField(max_length=100,null=True)
    actual_weight = models.DecimalField(max_digits=8, decimal_places=2)
    charged_weight = models.DecimalField(max_digits=8, decimal_places=2)
    freight = models.DecimalField(max_digits=10, decimal_places=2)
    lr_charge = models.DecimalField(max_digits=10, decimal_places=2)
    unloading_charge= models.DecimalField(max_digits=10, decimal_places=2)
    other_charge = models.DecimalField(max_digits=10, decimal_places=2)
    invoice_generated = models.BooleanField(default=False)

    def total_amount(self):
        return self.freight + self.lr_charge+self.unloading_charge+self.other_charge 


class CnoteBilling(models.Model):
    INV_PENDING = "PENDING"
    INV_INVOICED = "INVOICED"
    STATUS = [
        (INV_PENDING,"Pending"),
        (INV_INVOICED,"Invoiced")
    ]
    cnote = models.ForeignKey(CnoteModel,on_delete=models.CASCADE)
    consignor = models.ForeignKey(BillingConsignor,on_delete=models.CASCADE)
    payment = models.CharField(max_length=50)
    inv_freight = models.IntegerField()
    inv_lr =  models.IntegerField()
    inv_unloading = models.IntegerField()
    inv_other = models.IntegerField()
    status = models.CharField(max_length=50,choices=STATUS)

    def total_amount(self):
        return self.inv_freight + self.inv_lr+self.inv_unloading+self.inv_other 
    
    class Meta:
        db_table = "cnote_billing"
