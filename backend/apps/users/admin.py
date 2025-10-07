from django.contrib import admin

# Register your models here.

from .models import TelegramUser, Wallet, Transfer
admin.site.register(TelegramUser)
admin.site.register(Wallet)
admin.site.register(Transfer)
