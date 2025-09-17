import os
from bot_backend.apps.users.models import TelegramUser, Wallet
from bot_backend.apps.users.crypto import encrypt_secret
from bot_backend.apps.users.xrpl_service import create_user_wallet
from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help = "Create a dummy Telegram user with an XRPL wallet for testing."

    def handle(self, *args, **options):
        # Check if dummy user already exists
        if TelegramUser.objects.filter(telegram_id=999999999).exists():
            # Delete existing dummy user and wallet
            TelegramUser.objects.filter(telegram_id=999999999).delete()
            self.stdout.write(self.style.WARNING("Deleted existing dummy user."))

        # 1. Create a dummy Telegram user
        user = TelegramUser.objects.create(
            telegram_id=999999999,
            username="dummyuser",
            first_name="Dummy",
            last_name="User",
            is_active=True,
        )

        # 2. Create and fund an XRPL wallet
        wallet_data = create_user_wallet()
        if not wallet_data:
            raise CommandError("Failed to create XRPL wallet")

        # 3. Encrypt the seed using Fernet (key from env)
        encrypted_seed = encrypt_secret(wallet_data.seed)

        # 4. Create the Wallet object
        Wallet.objects.create(
            user=user,
            network="testnet",
            address=wallet_data.classic_address,
            secret_encrypted=encrypted_seed
        )
        self.stdout.write(self.style.SUCCESS(
            f"Created dummy user {user.display_name()} with wallet {wallet_data.classic_address}"
        ))
