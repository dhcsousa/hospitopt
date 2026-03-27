import reflex as rx


def metric_card(
    label: str,
    value: rx.Var | int,
    helper: str,
    alert_level: rx.Var | str = "normal",
) -> rx.Component:
    return rx.el.div(
        rx.el.p(
            label,
            class_name=rx.cond(
                alert_level == "critical",
                "text-xs font-medium text-rose-800",
                rx.cond(
                    alert_level == "warning",
                    "text-xs font-medium text-amber-800",
                    "text-xs font-medium text-slate-500",
                ),
            ),
        ),
        rx.el.h3(
            value,
            class_name=rx.cond(
                alert_level == "critical",
                "text-2xl font-semibold text-rose-950",
                rx.cond(
                    alert_level == "warning",
                    "text-2xl font-semibold text-amber-950",
                    "text-2xl font-semibold text-slate-900",
                ),
            ),
        ),
        rx.el.p(
            helper,
            class_name=rx.cond(
                alert_level == "critical",
                "text-xs text-rose-700",
                rx.cond(
                    alert_level == "warning",
                    "text-xs text-amber-700",
                    "text-xs text-slate-400",
                ),
            ),
        ),
        class_name=rx.cond(
            alert_level == "critical",
            "rounded-xl border border-rose-300 bg-rose-50 p-4 shadow-sm",
            rx.cond(
                alert_level == "warning",
                "rounded-xl border border-amber-300 bg-amber-50 p-4 shadow-sm",
                "rounded-xl border border-slate-200 bg-white p-4 shadow-sm",
            ),
        ),
    )
