from django.db import models

class TelegramUser(models.Model):
    telegram_id = models.BigIntegerField(unique=True, db_index=True)
    username = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    first_name = models.CharField(max_length=128, null=True, blank=True)
    last_name = models.CharField(max_length=128, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def display_name(self):
        return self.username or f"{self.first_name or ''} {self.last_name or ''}".strip() or str(self.telegram_id)

class Wallet(models.Model):
    NETWORK_CHOICES = [("testnet", "TestNet"), ("mainnet", "MainNet")]
    user = models.OneToOneField(TelegramUser, on_delete=models.CASCADE, related_name="wallet")
    network = models.CharField(max_length=16, choices=NETWORK_CHOICES, default="testnet")
    address = models.CharField(max_length=64, unique=True)  # r...
    secret_encrypted = models.BinaryField()                 # Fernet-encrypted seed/secret
    funded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Transfer(models.Model):
    STATUS = [("pending", "Pending"), ("validated", "Validated"), ("failed", "Failed")]
    sender = models.ForeignKey(TelegramUser, on_delete=models.SET_NULL, null=True, related_name="outgoing")
    recipient = models.ForeignKey(TelegramUser, on_delete=models.SET_NULL, null=True, related_name="incoming")
    destination_address = models.CharField(max_length=64)
    amount_drops = models.BigIntegerField()  # 1 XRP = 1,000,000 drops
    tx_hash = models.CharField(max_length=128, null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
