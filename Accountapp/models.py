from django.db import models,transaction
from Staffapp.models import CnoteModel
from Adminapp.models import Branch
from decimal import Decimal, ROUND_HALF_UP
import uuid

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

    group = models.ForeignKey("Billingapp.Groups", null=True, blank=True, on_delete=models.SET_NULL)
    def save(self, *args, **kwargs):
        from Billingapp.models import Groups
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

        if self.billing_payment:
            if self.billing_payment.upper() == "PAID":
                self.group = Groups.objects.filter(group_name__iexact="Paid Receivables").first()
            elif self.billing_payment.upper() == "CREDIT":
                self.group = Groups.objects.filter(group_name__iexact="Credit Receivables").first()

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
    cgst = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    sgst = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    igst = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    roundoff = models.DecimalField(max_digits=10, decimal_places=2, null=True)

    def total_amount(self):
        shipment_total = sum(Decimal(s.total_amount()) for s in self.couriershipment_set.all())
        billing_total = sum(Decimal(b.total_amount()) for b in self.cnotebilling_set.all())
        taxable_value = base_total = shipment_total + billing_total

        gst_type = self.customer.billing_consignor_gsttype

        cgst = sgst = igst = Decimal('0')
        round_off = Decimal('0')

        if gst_type == "REGULAR":
            cgst = (base_total * Decimal('0.09')).quantize(Decimal('0.01'))
            sgst = (base_total * Decimal('0.09')).quantize(Decimal('0.01'))
            total_invoice = base_total + cgst + sgst

        elif gst_type == "IGST":
            igst = (base_total * Decimal('0.18')).quantize(Decimal('0.01'))
            total_invoice = base_total + igst

        elif gst_type == "REVERSE":
            cgst = (base_total * Decimal('0.025')).quantize(Decimal('0.01'))
            sgst = (base_total * Decimal('0.025')).quantize(Decimal('0.01'))
            total_invoice = base_total  

        else:
            total_invoice = base_total

        total_invoice_rounded = total_invoice.to_integral_value(rounding=ROUND_HALF_UP)
        round_off = total_invoice_rounded - total_invoice


        self.cgst = cgst
        self.sgst = sgst
        self.igst = igst
        self.roundoff = round_off.quantize(Decimal('0.01'))

        return total_invoice

    def create_accounting_entry(self):
        from Billingapp.models import Ledger, Entry, Groups
        total = self.total_amount()
        transaction_id = str(uuid.uuid4())

        # Taxable value
        taxable_value = total - (self.cgst + self.sgst + self.igst + self.roundoff)

        sales_ledger = Ledger.objects.filter(ledger_name__iexact="Sales Account").first()
        customer_group = self.customer.group or Groups.objects.filter(group_name__iexact="Credit Receivables").first()
        customer_ledger, _ = Ledger.objects.get_or_create(
            ledger_name=self.customer.billing_consignor_name,
            defaults={"group": customer_group, "opening_balance": 0}
        )

        with transaction.atomic():
            # Customer entry
            Entry.objects.create(
                date=self.invoice_date,
                ledger=customer_ledger,
                debit=total,
                credit=0,
                voucher_type="Sales",
                transaction_id=transaction_id,
                invoice=self
            )

            # Sales ledger
            Entry.objects.create(
                date=self.invoice_date,
                ledger=sales_ledger,
                debit=0,
                credit=taxable_value,
                voucher_type="Sales",
                transaction_id=transaction_id,
                invoice=self
            )

            # GST entries
            if self.cgst > 0:
                cgst_ledger, _ = Ledger.objects.get_or_create(ledger_name="CGST Payable")
                Entry.objects.create(
                    date=self.invoice_date,
                    ledger=cgst_ledger,
                    debit=0,
                    credit=self.cgst,
                    voucher_type="Sales",
                    transaction_id=transaction_id
                )

            if self.sgst > 0:
                sgst_ledger, _ = Ledger.objects.get_or_create(ledger_name="SGST Payable")
                Entry.objects.create(
                    date=self.invoice_date,
                    ledger=sgst_ledger,
                    debit=0,
                    credit=self.sgst,
                    voucher_type="Sales",
                    transaction_id=transaction_id
                )

            if self.igst > 0:
                igst_ledger, _ = Ledger.objects.get_or_create(ledger_name="IGST Payable")
                Entry.objects.create(
                    date=self.invoice_date,
                    ledger=igst_ledger,
                    debit=0,
                    credit=self.igst,
                    voucher_type="Sales",
                    transaction_id=transaction_id
                )

            # Round-off entry (can be positive or negative)
            if self.roundoff != 0:
                round_off_ledger, _ = Ledger.objects.get_or_create(ledger_name="Round-Off")
                if self.roundoff > 0:
                    Entry.objects.create(
                        date=self.invoice_date,
                        ledger=round_off_ledger,
                        debit=0,
                        credit=self.roundoff,
                        voucher_type="Sales",
                        transaction_id=transaction_id
                    )
                else:
                    Entry.objects.create(
                        date=self.invoice_date,
                        ledger=round_off_ledger,
                        debit=abs(self.roundoff),
                        credit=0,
                        voucher_type="Sales",
                        transaction_id=transaction_id
                    )

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


