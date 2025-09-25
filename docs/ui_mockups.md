
## UI Mockups

### Start
```
👤 User: /start
🤖 Bot:
🚀 Welcome to XRPL Bot, Marc!

I'll help you manage XRP on the XRPL TestNet.

We created your account. You can use /help to see available commands.
```

### Help
```
👤 User: /help
🤖 Bot:
📋 Available Commands:

/start - Get started with the bot
/balance - Check your XRP balance
/send @username amount - Send XRP to another user
/prices [symbol] [days] - Get price history (default: XRP, 30 days)
/prices [symbol] [start] [end] - Use a custom range (YYYY-MM-DD)
/wallet - Create a new XRPL wallet
/help - Show this help message

Example: /send @alice 10.5
```

### Balance
```
👤 User: /balance
🤖 Bot:
💰 Your balance: 123.45 XRP
```
### Send
```
👤 User: /send @alice 10.5
🤖 Bot:
⏳ Sending 10.5 XRP to @alice...
✅ Sent 10.5 XRP to @alice!
TX Hash: 1234ABCD5678...
```
### Prices
```
👤 User: /prices xrp 7
🤖 Bot:
📈 XRP price history
Range: 2025-09-18 → 2025-09-25

• 2025-09-18: USD: $0.5270 | ZAR: R9.8650
• ...
📊 Change: USD: +2.15% | ZAR: +2.34%
```

### Wallet
```
👤 User: /wallet
🤖 Bot:
🆕 Wallet created!
Address: rEXAMPLE12345...
You have been credited with some test XRP.
Use /balance to check your balance.
```

### Error Handling

Error handling is uniform across all commands:
```
👤 User: /send @bob 1000
🤖 Bot:
❌ Insufficient balance. Your current balance is 123.45 XRP.    
```
