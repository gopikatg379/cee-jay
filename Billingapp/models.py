from django.db import models


class Groups(models.Model):
    group_name = models.CharField(max_length=100)
    under = models.CharField(max_length=50,choices=[
        ('Income', 'Income'),
        ('Asset', 'Asset'),
        ('Expense', 'Expense'),
        ('Liability', 'Liability'),
    ])
    def __str__(self):
        return self.group_name

class Ledger(models.Model):
    ledger_name = models.CharField(max_length=100)
    group = models.ForeignKey(Groups,on_delete=models.CASCADE,null=True)
    opening_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def __str__(self):
        return self.ledger_name

class Entry(models.Model):
    date = models.DateField()
    ledger = models.ForeignKey(Ledger, on_delete=models.CASCADE)
    debit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    voucher_type = models.CharField(max_length=20,null=True)  
    transaction_id = models.CharField(max_length=50, null=True, blank=True) 
    remarks = models.TextField(null=True, blank=True)
    invoice = models.ForeignKey('Accountapp.Invoice', on_delete=models.SET_NULL, null=True, blank=True)
    def __str__(self):
        return f"{self.ledger.ledger_name} - {self.date}"
    
    
class Payment(models.Model):
    ledger = models.ForeignKey(Ledger, on_delete=models.CASCADE)
    payment_type = models.CharField(max_length=10, choices=[('Credit','Credit'),('Debit','Debit')])
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField()
    mode = models.CharField(max_length=20, blank=True)
    remarks = models.TextField(blank=True)

    def __str__(self):
        return f"{self.ledger.name} - {self.amount}"