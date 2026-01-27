from django.db import models, transaction
from django.db.models import Max
from Adminapp.models import Consignee,Consignor,Location,Item,Branch
from decimal import Decimal

class CnoteModel(models.Model):
    STATUS_NEW = 'NEW'
    STATUS_DISPATCHED = 'DISPATCHED'
    STATUS_DELIVERED = 'DELIVERED'
    STATUS_CHOICES = [
        (STATUS_NEW, 'New'),
        (STATUS_DISPATCHED, 'Dispatched'),
        (STATUS_DELIVERED, 'Delivered'),
    ]
    cnote_id = models.AutoField(primary_key=True)
    date = models.DateField()

    reference_no = models.CharField(max_length=30)
    payment = models.CharField(max_length=30)

    consignor = models.ForeignKey(Consignor,on_delete=models.PROTECT)
    consignee = models.ForeignKey(Consignee,on_delete=models.PROTECT)
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

    actual_weight = models.DecimalField(max_digits=10, decimal_places=2,null=True)
    charged_weight = models.DecimalField(max_digits=10, decimal_places=2,null=True)

    total_item = models.PositiveIntegerField()

    freight=models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "cnote_table"
    def save(self, *args, **kwargs):
        if not self.cnote_number:  
            with transaction.atomic(): 
                prefix = ""
                if self.booking_branch:
                    prefix = (self.booking_branch.branch_shortname or "").upper().strip()

                if not prefix:
                    prefix = "GEN"  

                last = (
                    CnoteModel.objects
                    .filter(cnote_number__startswith=prefix)
                    .aggregate(max_num=Max('cnote_number'))
                    ['max_num']
                )

                if last:

                    num = int(last[len(prefix):]) + 1
                else:
                    num = 10000   

                self.cnote_number = f"{prefix}{num}"

        super().save(*args, **kwargs)

class CnoteItem(models.Model):
    cnote = models.ForeignKey('CnoteModel', on_delete=models.CASCADE, related_name='items')
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    qty = models.PositiveIntegerField()
    rate = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "cnote_item_table"