import reflex as rx


def metric_card(label: str, value: rx.Var | int, helper: str) -> rx.Component:
    return rx.el.div(
        rx.el.p(label, class_name="text-xs font-medium text-slate-500"),
        rx.el.h3(value, class_name="text-2xl font-semibold text-slate-900"),
        rx.el.p(helper, class_name="text-xs text-slate-400"),
        class_name="rounded-xl border border-slate-200 bg-white p-4 shadow-sm",
    )
