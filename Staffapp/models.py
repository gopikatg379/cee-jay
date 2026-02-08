from django.db import models, transaction
from django.db.models import Max
from Adminapp.models import *
from decimal import Decimal
from django.utils import timezone


class ManifestModel(models.Model):
    MANIFEST_BRANCH = 'BRANCH'
    MANIFEST_DELIVERY = 'DELIVERY'

    MANIFEST_TYPES = [
        (MANIFEST_BRANCH, 'Branch Transfer'),
        (MANIFEST_DELIVERY, 'Delivery'),
    ]
    manifest_id = models.AutoField(primary_key=True)
    date = models.DateField()
    driver = models.ForeignKey(Driver,on_delete=models.PROTECT)
    vehicle = models.ForeignKey(Vehicle,on_delete=models.PROTECT)
    branch = models.ForeignKey(Branch,on_delete=models.PROTECT,null=True)
    manifest_type = models.CharField(max_length=20, choices=MANIFEST_TYPES)
    
    class Meta:
        db_table = 'manifest_table'

    def __str__(self):
        return f"Manifest {self.manifest_id}"
    

class CnoteModel(models.Model):
    STATUS_NEW = 'NEW'
    STATUS_RECEIVED = 'RECEIVED'
    STATUS_INTRANSIT = 'SHIPPED'
    STATUS_DISPATCHED = 'OUT FOR DELIVERY'
    STATUS_DELIVERED = 'DELIVERED'
    STATUS_CANCEL = 'Cancelled'
    STATUS_CHOICES = [
        (STATUS_NEW, 'New'),
        (STATUS_RECEIVED, 'Received'),
        (STATUS_INTRANSIT, 'Shipped'),
        (STATUS_DISPATCHED, 'Out For Delivery'),
        (STATUS_DELIVERED, 'Delivered'),
        (STATUS_CANCEL,'Cancelled')
    ]
    received_at = models.DateTimeField(null=True, blank=True)
    received_branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="received_cnotes"
    )
    received_by = models.ForeignKey(
        UserModel,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="received_cnotes"
    )

    cnote_id = models.AutoField(primary_key=True)
    date = models.DateField()

    reference_no = models.CharField(max_length=30)
    payment = models.CharField(max_length=30)

    consignor = models.ForeignKey(Consignor,on_delete=models.PROTECT)
    consignee = models.ForeignKey(Consignee,on_delete=models.PROTECT)
    consignee_phone = models.CharField(max_length=12,null=True)
    booking_branch = models.ForeignKey(Branch,on_delete=models.PROTECT,related_name="booking_cnotes",null=True)
    delivery_branch = models.ForeignKey(Branch,on_delete=models.PROTECT,null=True,related_name="delivery_cnotes")

    destination = models.ForeignKey(Location,on_delete=models.PROTECT)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_NEW
    )
    cnote_number = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
        null=True,         
        verbose_name="CNote Number",
    )
    invoice_no = models.CharField(max_length=20,null=True)
    invoice_amt = models.DecimalField(max_digits=10, decimal_places=2,null=True)

    lr_charge = models.DecimalField(max_digits=10, decimal_places=2,null=True)
    pickup_charge = models.DecimalField(max_digits=10, decimal_places=2,null=True)
    hamali_charge = models.DecimalField(max_digits=10, decimal_places=2,null=True)
    unloading_charge = models.DecimalField(max_digits=10, decimal_places=2,null=True)
    door_delivery = models.DecimalField(max_digits=10, decimal_places=2,null=True)
    other_charge = models.DecimalField(max_digits=10, decimal_places=2,null=True)

    delivery_type = models.CharField(max_length=30)

    eway_no = models.CharField(max_length=50,null=True)
    actual_weight = models.DecimalField(max_digits=10, decimal_places=2,null=True)
    charged_weight = models.DecimalField(max_digits=10, decimal_places=2,null=True)

    total_item = models.PositiveIntegerField()

    freight=models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2)

    remarks = models.TextField(blank=True,null=True)
    user = models.ForeignKey(UserModel,on_delete=models.PROTECT,null=True)
    manifest = models.ForeignKey(
        ManifestModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cnotes"
    )
    created_at = models.DateTimeField(auto_now_add=True,null=True)
    class Meta:
        db_table = "cnote_table"
    def save(self, *args, **kwargs):
        is_new = self.pk is None

        if not is_new:
            old = CnoteModel.objects.get(pk=self.pk)

            if old.status != self.STATUS_RECEIVED and self.status == self.STATUS_RECEIVED:
                if not self.received_at:
                    self.received_at = timezone.now()

        if not self.cnote_number:
            with transaction.atomic():

                if not self.booking_branch or not self.booking_branch.branch_code:
                    prefix = "GEN"
                else:
                    prefix = str(self.booking_branch.branch_code)

                last_cnote = (
                    CnoteModel.objects
                    .filter(cnote_number__startswith=f"{prefix}-")
                    .aggregate(max_num=Max('cnote_number'))
                    .get('max_num')
                )
                if last_cnote:
                    last_running = int(last_cnote.split("-")[1])
                    next_running = last_running + 1
                else:
                    next_running = 10000

                self.cnote_number = f"{prefix}-{next_running}"

        super().save(*args, **kwargs)

class CnoteItem(models.Model):
    cnote = models.ForeignKey('CnoteModel', on_delete=models.CASCADE, related_name='items')
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    qty = models.PositiveIntegerField()
    rate = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "cnote_item_table"

class CnoteTracking(models.Model):
    cnote = models.ForeignKey(
        CnoteModel,
        on_delete=models.CASCADE,
        related_name="trackings"
    )
    status = models.CharField(max_length=30)
    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )
    manifest = models.ForeignKey(
        ManifestModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        UserModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    class Meta:
        ordering = ["created_at"]


