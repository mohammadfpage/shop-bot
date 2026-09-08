"""
Finite State Machine states for every product workflow.

Each group of states belongs to one feature so that FSMHandler / Router
can target exactly the right handler set.
"""

from aiogram.fsm.state import State, StatesGroup


# ─── Telegram Premium ────────────────────────────────────────────────
class TelegramPremiumStates(StatesGroup):
    """Choose duration → own/other account → pay."""
    choose_duration = State()   # monthly / quarterly / semi_annual / yearly
    choose_target = State()     # own or other
    enter_other_id = State()    # target Telegram user-id if "other"
    payment = State()           # waiting for payment link click & verify


# ─── Telegram Stars (Standard, custom quantity) ─────────────────────
class TelegramStarsStates(StatesGroup):
    """Enter stars qty (min 50) → own/other → pay."""
    enter_quantity = State()
    choose_target = State()
    enter_other_id = State()
    payment = State()


# ─── Telegram Stars Gifts (Fixed packages) ─────────────────────────
class TelegramStarsGiftStates(StatesGroup):
    """Choose gift package → pay → receive gift link."""
    choose_package = State()
    payment = State()


# ─── AI Accounts (ChatGPT & Gemini) ──────────────────────────────────
class AIAccountStates(StatesGroup):
    """Choose platform → pay → auto-deliver credentials."""
    choose_platform = State()   # chatgpt / gemini
    payment = State()
    deliver = State()


# ─── Design Services ─────────────────────────────────────────────────
class DesignServiceStates(StatesGroup):
    """Choose tier → describe project → pay → forward to admin."""
    choose_tier = State()       # AI / Simple / Normal / Special
    enter_description = State() # free-text project description
    enter_contact = State()     # how admin can reach you (username / phone)
    payment = State()


# ─── Page Security ───────────────────────────────────────────────────
class PageSecurityStates(StatesGroup):
    """View tariffs → fill request form → send to admin."""
    choose_tariff = State()
    enter_page_url = State()
    enter_details = State()
    confirm = State()


# ─── Ticket / Support ────────────────────────────────────────────────
class TicketStates(StatesGroup):
    """Support ticket: user sends message → forwarded to admin → admin replies."""
    waiting_message = State()       # waiting for user's ticket message
    admin_reply = State()           # admin is typing a reply to a ticket


# ─── Product Price Editing (Inline Panel) ──────────────────────────
class ProductState(StatesGroup):
    """FSM for inline price editing panel.

    Flow:
        1. Admin taps a product button → product detail shown
        2. Admin taps "ویرایش قیمت" → state: waiting_for_price
        3. Admin sends new price text → DB updated, message edited to success
    """
    waiting_for_price = State()  # admin is typing the new USD price


# ─── Admin Panel ─────────────────────────────────────────────────────
class AdminStates(StatesGroup):
    """Admin-only FSM for price editing, broadcast, etc."""
    edit_price_key = State()
    edit_price_value = State()
    process_order_id = State()
    broadcast_message = State()     # waiting for broadcast text message
    broadcast_photo = State()       # waiting for broadcast photo
    waiting_for_ticket_reply = State()  # admin is typing a support reply to a user
