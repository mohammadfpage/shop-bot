"""Payment verification handlers for the Zarinpal REST v4 flow."""

import contextlib

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from database.db import (
    complete_payment,
    delete_payment,
    fail_payment,
    get_payment,
    update_order_status,
)
from keyboards.inline import back_to_menu_kb
from utils.delivery import deliver_product
from utils.zarinpal import verify_payment

router = Router(name="payment")


@router.callback_query(F.data == "pay:check")
async def cb_pay_check(callback: CallbackQuery, state: FSMContext) -> None:
    """Verify one persisted payment and deliver only after exact validation."""
    try:
        state_data = await state.get_data()
        payment_id = state_data.get("payment_id")
        state_order_id = state_data.get("order_id")
        state_authority = state_data.get("authority")

        if not payment_id or not state_order_id or not state_authority:
            await callback.answer("⚠️ پرداخت در انتظاری یافت نشد.", show_alert=True)
            return

        payment = await get_payment(payment_id)
        if not payment:
            await callback.answer("⚠️ اطلاعات پرداخت یافت نشد.", show_alert=True)
            return

        # Never trust mutable FSM values for the amount, authority, or order.
        if (
            payment["order_id"] != state_order_id
            or payment["authority"] != state_authority
            or payment["user_id"] != callback.from_user.id
            or payment["payment_status"] != "init"
            or payment["order_status"] != "pending"
            or payment["payment_amount_irt"] != payment["order_amount_irt"]
        ):
            await fail_payment(payment_id)
            await callback.answer("❌ اطلاعات پرداخت معتبر نیست.", show_alert=True)
            return

        await callback.answer("⏳ در حال بررسی پرداخت…", show_alert=False)
        result = await verify_payment(
            authority=payment["authority"],
            amount_irt=payment["order_amount_irt"],
        )

        # Zarinpal must confirm the exact IRT amount returned by the API.
        amount_matches = result.amount_irt == payment["order_amount_irt"]
        if not (
            result.success
            and result.code in (100, 101)
            and result.ref_id
            and amount_matches
        ):
            await fail_payment(payment_id)
            with contextlib.suppress(TelegramBadRequest):
                await callback.message.edit_text(
                    "❌ <b>بررسی پرداخت ناموفق بود.</b>\n\n"
                    f"دلیل: {result.message or 'مبلغ پرداخت با سفارش مطابقت ندارد.'}\n\n"
                    "اگر فکر می‌کنید این خطا است، لطفاً دوباره تلاش کنید یا با پشتیبانی تماس بگیرید.",
                    reply_markup=back_to_menu_kb(),
                )
            return

        # This conditional transition prevents duplicate fulfillment.
        completed = await complete_payment(
            payment_id=payment_id,
            order_id=payment["order_id"],
            ref_id=result.ref_id,
        )
        if not completed:
            await callback.answer("✅ این پرداخت قبلاً بررسی شده است.", show_alert=True)
            return

        await deliver_product(
            bot=callback.bot,
            user_id=payment["user_id"],
            order_id=payment["order_id"],
            product=payment["product"],
            details=payment["details"] or "",
            extra={"country": state_data.get("country", "iran")},
        )
    finally:
        # Clear stale payment context on success, failure, or handler errors.
        await state.clear()


@router.callback_query(F.data == "pay:cancel")
async def cb_pay_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """Cancel the current payment and remove its persisted payment record."""
    try:
        data = await state.get_data()
        payment_id = data.get("payment_id")
        order_id = data.get("order_id")

        if order_id:
            await update_order_status(order_id, "cancelled")
        if payment_id:
            await delete_payment(payment_id)

        with contextlib.suppress(TelegramBadRequest):
            await callback.message.edit_text(
                "❌ پرداخت لغو شد.\n\nبه منوی اصلی بازگردید:",
                reply_markup=back_to_menu_kb(),
            )
        await callback.answer()
    finally:
        await state.clear()
