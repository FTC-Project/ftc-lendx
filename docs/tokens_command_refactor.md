# Tokens Command Refactor Summary

## Overview

The `tokens` command has been fully refactored to match the architecture pattern used by other commands (like `register` and `apply`), implementing proper menu navigation with back/cancel functionality.

## Key Changes

### ✅ Architecture Consistency

1. **Proper Flow Control**
   - Uses `flow:back` and `flow:cancel` callbacks (not custom `tokens:back`)
   - Implements `PREV` mapping for step navigation
   - Uses `prev_step_of()` helper for backwards navigation

2. **FSM State Management**
   - Uses `set_step()` to advance through flow
   - Uses `mark_prev_keyboard()` before every reply
   - Properly clears flow on exit

3. **Menu System**
   - Main menu (S_MENU) → Balance view (S_BALANCE) or Tier view (S_TIER)
   - Back button returns to menu
   - Cancel/Back from menu exits the flow
   - Consistent keyboard management

### 📊 Flow Structure

```
/tokens
  ↓
S_MENU (Main Dashboard)
  ├─ "View Balance" → S_BALANCE
  │                      ↓ (back)
  │                    S_MENU
  ├─ "View Tier" → S_TIER
  │                   ↓ (back)
  │                 S_MENU
  └─ "Back" → Exit flow
```

### 🎨 User Experience Improvements

#### Before
- Inconsistent button handling
- Custom back button logic
- No proper flow navigation
- Plain text messages

#### After
- Standardized `flow:back` and `flow:cancel` buttons
- Proper step-by-step navigation
- Rich HTML formatted messages with emojis
- Clear instructional text
- Consistent error handling

### 💻 Code Quality

#### Improvements Made

1. **Removed unused imports**
   - `HelpCommand` (unused)
   - `kb_options` (replaced with manual keyboard)

2. **Added proper flow helpers**
   - `set_step` for advancing
   - `prev_step_of` for backwards navigation
   - `mark_prev_keyboard` for cleanup

3. **Consistent error handling**
   - Handles unknown callbacks
   - Handles text input when buttons expected
   - Clear error messages for users

4. **Better documentation**
   - Added docstring to class
   - Clear comments for each section
   - Organized callback handling

### 🔄 Callback Handling

#### Before
```python
if cb == "tokens:back":
    clear_flow(fsm, message.chat_id)
    # Show menu
    return
```

#### After
```python
if cb == "flow:cancel":
    clear_flow(fsm, msg.chat_id)
    mark_prev_keyboard(data, msg)
    reply(msg, "👋 Exiting CTT dashboard. Use /tokens to return anytime.", data=data)
    return

if cb == "flow:back":
    prev = prev_step_of(PREV, step)
    if prev is None:
        clear_flow(fsm, msg.chat_id)
        mark_prev_keyboard(data, msg)
        reply(msg, "👋 Exiting CTT dashboard.", data=data)
        return
    # Navigate to previous step
    set_step(fsm, msg.chat_id, CMD, prev, data)
    mark_prev_keyboard(data, msg)
    # Show appropriate content for previous step
    ...
```

### 📝 Message Formatting

#### Before
```python
reply(message, f"💰 Your CTT balance is: {balance} CTT", kb_back_cancel())
```

#### After
```python
reply(
    msg,
    f"💰 <b>Your CTT Balance</b>\n\n"
    f"<b>Balance:</b> {balance:,.2f} CTT\n\n"
    f"<i>Credit Trust Tokens represent your creditworthiness "
    f"and unlock better loan terms.</i>",
    kb_back_cancel(),
    data=data,
    parse_mode="HTML",
)
```

### 🔐 Permission Level

Maintained: `verified_borrower`
- User must be registered borrower
- User must have verified KYC
- Enforced by non-blocking permission check system

### 🎯 Step Definitions

```python
S_MENU = "tokens_menu"          # Main dashboard menu
S_BALANCE = "tokens_view_balance"  # Balance view screen
S_TIER = "tokens_view_tier"        # Tier information screen

PREV = {
    S_MENU: None,      # Back from menu = exit
    S_BALANCE: S_MENU, # Back from balance = menu
    S_TIER: S_MENU,    # Back from tier = menu
}
```

### 🧪 Testing Checklist

- [x] Command starts with menu
- [x] "View Balance" shows balance and allows back to menu
- [x] "View Tier" shows tier info and allows back to menu
- [x] Back button from balance/tier returns to menu
- [x] Back button from menu exits flow
- [x] Cancel button exits flow
- [x] Text input prompts to use buttons
- [x] Unknown callbacks handled gracefully
- [x] FSM state cleaned up on exit
- [x] Previous keyboards cleared properly
- [x] No linter errors

## Compatibility

✅ **Fully compatible** with:
- Non-blocking permission system
- Celery shared task architecture
- FSM flow management
- All other telegram bot commands

## Benefits

1. **Consistent UX**: Same back/cancel behavior as other commands
2. **Maintainable**: Follows established patterns
3. **Robust**: Proper error handling and state management
4. **Beautiful**: Rich HTML formatting with emojis
5. **Scalable**: Built on non-blocking Celery architecture

## Files Modified

- `backend/apps/telegram_bot/commands/tokens.py` - Complete rewrite following standard pattern

## No Breaking Changes

The command still:
- Uses `/tokens` to invoke
- Shows CTT balance
- Shows tier information
- Requires `verified_borrower` permission

