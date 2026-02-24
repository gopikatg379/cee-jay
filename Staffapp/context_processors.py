from django.db.models import Q, Sum, Case, When, F, Value, DecimalField
from .models import CnoteModel


def wallet_balance(request):

    if not request.user.is_authenticated:
        return {
            "wallet_balance": 0,
            "total_commission": 0,
            "total_collection": 0,
        }

    user = request.user

    if user.role == "ADMIN":
        return {
            "wallet_balance": None,
            "total_commission": None,
            "total_collection": None,
        }

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
                When(booking_branch=branch, then=F("booking_commission_amount")),
                default=Value(0),
                output_field=DecimalField()
            )
        ),
        delivery_commission=Sum(
            Case(
                When(delivery_branch=branch, then=F("delivery_commission_amount")),
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
                    Q(payment="PAID") & Q(booking_branch=branch),
                    then=F("total")
                ),
                default=Value(0),
                output_field=DecimalField()
            )
        ),
        topay_collection=Sum(
            Case(
                When(
                    Q(payment="TOPAY") & Q(delivery_branch=branch),
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

    return {
        "wallet_balance": wallet_balance,
        "total_commission": total_commission,
        "total_collection": total_collection,
    }