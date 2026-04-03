# -*- coding: utf-8 -*-

from handlers_object_analytics import (
    handle_object_finance_history,
    handle_object_activity_presence,
    handle_my_object_presence,
    handle_object_activity_timeline,
)

from handlers_finance_analytics import (
    handle_finance_turnover,
    handle_finance_gross_profit,
    handle_finance_objects_summary,
)

from features.employee_absences import (
    handle_employee_absences_total,
    handle_employee_absences_disputed,
    handle_employee_absences_month,
    handle_employee_absences_month_details,
)

from handlers_employee_time import (
    handle_employee_time_total,
    handle_employee_time_month,
    handle_employee_time_month_object,
    handle_employee_time_days_month,
    handle_employee_time_days_month_object,
    handle_employee_time_day_timeline,
    handle_employee_time_day_object_timeline,
)
from features.employee_attendance import (
    handle_employee_attendance_month_summary,
    handle_employee_attendance_day_details,
)
from features.employee_calendar import (
    handle_employee_calendar_day_period,
    handle_employee_calendar_day_upcoming,
)

from features.employee_finance import (
    handle_employee_finance_month_list,
    handle_employee_finance_month_total,
    handle_employee_finance_total,
    handle_employee_finance_cash_plan,
)

from handlers_payroll import (
    handle_payroll_queue,
    handle_payroll_history,
)

from handlers_dispatcher_withhold import (
    handle_dispatcher_withhold_accrual_year_total,
    handle_dispatcher_withhold_accrual_year_percent_avg,
    handle_dispatcher_withhold_accrual_month_total,
    handle_dispatcher_withhold_accrual_month_percent_avg,
    handle_dispatcher_withhold_accrual_user_total,
    handle_dispatcher_withhold_accrual_user_total_all_firms,
)
from handlers_dispatcher_settlement import (
    handle_dispatcher_settlement_queue,
)

from features.worker_home import (
    handle_worker_month_deals_and_shifts,
    handle_worker_day_deals_and_shifts_all_firms,
    handle_worker_month_deals_and_shifts_all_firms,
    handle_worker_fines_year_total,
    handle_worker_fines_month_list,
    handle_worker_fines_year_list_excluding_month,
    handle_worker_fines_totals_all_firms,
    handle_worker_fines_list_all_firms,
    handle_worker_absences_list_all_firms,
)

__all__ = [
    "handle_object_finance_history",
    "handle_object_activity_presence",
    "handle_my_object_presence",
    "handle_object_activity_timeline",
    "handle_finance_turnover",
    "handle_finance_gross_profit",
    "handle_finance_objects_summary",
    "handle_employee_absences_total",
    "handle_employee_absences_disputed",
    "handle_employee_absences_month",
    "handle_employee_absences_month_details",
    "handle_employee_time_total",
    "handle_employee_time_month",
    "handle_employee_time_month_object",
    "handle_employee_time_days_month",
    "handle_employee_time_days_month_object",
    "handle_employee_time_day_timeline",
    "handle_employee_time_day_object_timeline",
    "handle_employee_attendance_month_summary",
    "handle_employee_attendance_day_details",
    "handle_employee_calendar_day_period",
    "handle_employee_calendar_day_upcoming",
    "handle_employee_finance_month_list",
    "handle_employee_finance_month_total",
    "handle_employee_finance_total",
    "handle_employee_finance_cash_plan",
    "handle_payroll_queue",
    "handle_payroll_history",
    "handle_dispatcher_withhold_accrual_year_total",
    "handle_dispatcher_withhold_accrual_year_percent_avg",
    "handle_dispatcher_withhold_accrual_month_total",
    "handle_dispatcher_withhold_accrual_month_percent_avg",
    "handle_dispatcher_withhold_accrual_user_total",
    "handle_dispatcher_withhold_accrual_user_total_all_firms",
    "handle_dispatcher_settlement_queue",
    "handle_worker_month_deals_and_shifts",
    "handle_worker_day_deals_and_shifts_all_firms",
    "handle_worker_month_deals_and_shifts_all_firms",
    "handle_worker_fines_year_total",
    "handle_worker_fines_month_list",
    "handle_worker_fines_year_list_excluding_month",
    "handle_worker_fines_totals_all_firms",
    "handle_worker_fines_list_all_firms",
    "handle_worker_absences_list_all_firms",
]
