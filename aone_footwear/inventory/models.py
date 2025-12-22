 
# inventory/models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# Master tables (dimension tables) --------------------

class Brand(TimeStampedModel):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Category(TimeStampedModel):
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=100)

    class Meta:
        unique_together = ('brand', 'name')

    def __str__(self):
        return f'{self.brand} - {self.name}'


class Section(TimeStampedModel):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='sections')
    name = models.CharField(max_length=100)

    class Meta:
        unique_together = ('category', 'name')

    def __str__(self):
        return f'{self.category} - {self.name}'


class Size(TimeStampedModel):
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name='sizes')
    value = models.CharField(max_length=20)

    class Meta:
        unique_together = ('section', 'value')

    def __str__(self):
        return f'{self.section} - {self.value}'


class Supplier(TimeStampedModel):
    name = models.CharField(max_length=150)
    mobile = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


class Customer(TimeStampedModel):
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    due_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return self.name


class Product(TimeStampedModel):
    """Unique article (Brand+Cat+Section+Size+MRP)"""
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT)
    category = models.ForeignKey(Category, on_delete=models.PROTECT)
    section = models.ForeignKey(Section, on_delete=models.PROTECT)
    size = models.ForeignKey(Size, on_delete=models.PROTECT)
    article_no = models.CharField(max_length=100, blank=True)
    mrp = models.DecimalField(max_digits=10, decimal_places=2)
    default_discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=10)  # 10% default
    gst_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    class Meta:
        indexes = [
            models.Index(fields=['brand', 'category', 'section', 'size']),
        ]

    def __str__(self):
        return f'{self.brand}/{self.category}/{self.section}/{self.size} - {self.mrp}'


class Stock(TimeStampedModel):
    """Aggregated stock for each product"""
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name='stock')
    quantity = models.IntegerField(default=0)

    def __str__(self):
        return f'{self.product} ({self.quantity})'


# Purchase (stock in) ---------------------------------

class PurchaseBill(TimeStampedModel):
    PAYMENT_CHOICES = (
        ('CASH', 'Cash'),
        ('CREDIT', 'Credit'),
    )

    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    bill_number = models.CharField(max_length=50)
    bill_date = models.DateField()
    entry_date = models.DateTimeField(default=timezone.now)
    total_qty = models.IntegerField(default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_gst = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_mode = models.CharField(max_length=10, choices=[("CASH","Cash"),("CREDIT","Credit")])
    cash_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    credit_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return f"{self.supplier} - {self.bill_number}"

    class Meta:
        unique_together = ('supplier', 'bill_number')


class PurchaseItem(TimeStampedModel):
    purchase = models.ForeignKey(PurchaseBill, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)

    quantity = models.IntegerField()
    mrp = models.DecimalField(max_digits=10, decimal_places=2)
    billing_price = models.DecimalField(max_digits=10, decimal_places=2)

    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    gst_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    gst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    line_total = models.DecimalField(max_digits=12, decimal_places=2)
    msp = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f'{self.purchase} - {self.product}'


# Sales / Billing -------------------------------------

class SalesBill(TimeStampedModel):
    PAYMENT_CHOICES = (
        ('CASH', 'Cash'),
        ('CREDIT', 'Credit'),
        ('UPI', 'UPI'),
        ('CARD', 'Card'),
    )

    bill_number = models.CharField(max_length=50)
    bill_date = models.DateTimeField(default=timezone.now)
    customer = models.ForeignKey(Customer, null=True, blank=True,
                                 on_delete=models.SET_NULL)
    payment_mode = models.CharField(max_length=10, choices=PAYMENT_CHOICES, default='CASH')
    total_qty = models.IntegerField(default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_gst = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cgst = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sgst = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)

    def __str__(self):
        return f'Sales #{self.id} - {self.bill_number}'


class SalesItem(TimeStampedModel):
    sales_bill = models.ForeignKey(SalesBill, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.IntegerField()
    mrp = models.DecimalField(max_digits=10, decimal_places=2)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    gst_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    gst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def __str__(self):
        return f'{self.sales_bill} - {self.product}'

class ExpenseCategory(models.Model):
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Expense(models.Model):
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    expense_date = models.DateField()
    payment_mode = models.CharField(
        max_length=20,
        choices=[('CASH','Cash'), ('BANK','Bank'), ('UPI','UPI')]
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
