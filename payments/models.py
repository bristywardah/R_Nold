from django.db import models
from django.conf import settings
from django.db.models import Sum
from django.utils.timezone import now
from payments.enums import PaymentStatusEnum, PaymentMethodEnum
from users.models import BaseModel


class Payment(BaseModel):

    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.CASCADE,
        related_name='payments',
        null=True,  
        blank=True  
    )


    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="payments",
        null=True,  
        blank=True 
    )



    vendor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="vendor_payments",
        limit_choices_to={"role": "vendor"}
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="customer_payments",
        limit_choices_to={"role": "customer"}
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(
        max_length=20,
        choices=[(tag.value, tag.value) for tag in PaymentMethodEnum],
        default=PaymentMethodEnum.STRIPE.value
    )
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=[(tag.value, tag.value) for tag in PaymentStatusEnum],
        default=PaymentStatusEnum.PENDING.value
    )

    note = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Payment #{self.id} - {self.product.name} - {self.status}"

    @classmethod
    def get_total_payment_count(cls):
        """Return total count of completed payments"""
        return cls.objects.filter(status=PaymentStatusEnum.COMPLETED.value).count()

    @classmethod
    def get_total_payments(cls):
        """Return total sum amount of completed payments"""
        result = cls.objects.filter(status=PaymentStatusEnum.COMPLETED.value)\
            .aggregate(total=Sum('amount'))
        return result['total'] or 0

    @classmethod
    def get_total_payment_count_for_user(cls, user):
        """Return total count of completed payments for a specific user"""
        return cls.objects.filter(customer=user, status=PaymentStatusEnum.COMPLETED.value).count()

    @classmethod
    def get_total_payments_for_user(cls, user):
        """Return total sum amount of completed payments for a specific user"""
        result = cls.objects.filter(
            customer=user,
            status=PaymentStatusEnum.COMPLETED.value
        ).aggregate(total=Sum('amount'))
        return result['total'] or 0

    @classmethod
    def get_yearly_payments(cls, year=None, user=None):
        """Return total payments amount in a specific year, optionally filtered by user"""
        if year is None:
            year = now().year

        qs = cls.objects.filter(
            created_at__year=year,
            status=PaymentStatusEnum.COMPLETED.value
        )
        if user:
            qs = qs.filter(customer=user)

        result = qs.aggregate(total=Sum('amount'))
        return result['total'] or 0

    @classmethod
    def get_monthly_payments(cls, year=None, month=None, user=None):
        """Return total payments amount in a specific month/year, optionally filtered by user"""
        current = now()
        if year is None:
            year = current.year
        if month is None:
            month = current.month

        qs = cls.objects.filter(
            created_at__year=year,
            created_at__month=month,
            status=PaymentStatusEnum.COMPLETED.value
        )
        if user:
            qs = qs.filter(customer=user)

        result = qs.aggregate(total=Sum('amount'))
        return result['total'] or 0
