from django.contrib import admin
from .models import PoolAccount, PoolDeposit, PoolWithdrawal, PoolSnapshot


@admin.register(PoolAccount)
class PoolAccountAdmin(admin.ModelAdmin):
    list_display = ("user", "principal", "accrued_interest", "updated_at")
    search_fields = ("user__username",)


@admin.register(PoolDeposit)
class PoolDepositAdmin(admin.ModelAdmin):
    list_display = ("user", "amount", "tx_hash", "created_at")
    search_fields = ("tx_hash", "user__username")
    date_hierarchy = "created_at"


@admin.register(PoolWithdrawal)
class PoolWithdrawalAdmin(admin.ModelAdmin):
    list_display = ("user", "principal_out", "interest_out", "tx_hash", "created_at")
    search_fields = ("tx_hash", "user__username")
    date_hierarchy = "created_at"


@admin.register(PoolSnapshot)
class PoolSnapshotAdmin(admin.ModelAdmin):
    list_display = ("at", "total_pool", "total_principal", "acc_interest_per_share")
