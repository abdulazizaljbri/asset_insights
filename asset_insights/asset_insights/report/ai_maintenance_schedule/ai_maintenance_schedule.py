# Copyright (c) 2026, Asset Insights Team
# License: MIT
# Maintenance Schedule — جدول الصيانة الدورية
# Real v15 tables: `tabAsset Maintenance` (am) + child
# `tabAsset Maintenance Task` (amt) + `tabAsset` (a via am.asset_name).
# Drafts only when Include Drafts is ticked.

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate, add_months

from asset_insights.asset_insights.utils import (
	drafts_clause,
	MAINTENANCE_TASK_STATUSES,
)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	# default window: due dates from today for the next 3 months
	filters.due_from = filters.get("due_from") or getdate(nowdate())
	filters.due_to = filters.get("due_to") or add_months(getdate(nowdate()), 3)

	columns = get_columns()
	data, message, chart = get_data(filters)
	return columns, data, message, chart


def get_columns():
	return [
		{"label": _("Asset ID"), "fieldname": "asset", "fieldtype": "Link", "options": "Asset", "width": 150},
		{"label": _("Asset Name"), "fieldname": "asset_name", "fieldtype": "Data", "width": 170},
		{"label": _("Asset Category"), "fieldname": "asset_category", "fieldtype": "Link", "options": "Asset Category", "width": 130},
		{"label": _("Task"), "fieldname": "maintenance_task", "fieldtype": "Data", "width": 190},
		{"label": _("Maintenance Type"), "fieldname": "maintenance_type", "fieldtype": "Data", "width": 140},
		{"label": _("Periodicity"), "fieldname": "periodicity", "fieldtype": "Data", "width": 100},
		{"label": _("Maintenance Status"), "fieldname": "maintenance_status", "fieldtype": "Data", "width": 130},
		{"label": _("Next Due Date"), "fieldname": "next_due_date", "fieldtype": "Date", "width": 120},
		{"label": _("Days Until Due"), "fieldname": "days_until_due", "fieldtype": "Int", "width": 120},
		{"label": _("Last Completion Date"), "fieldname": "last_completion_date", "fieldtype": "Date", "width": 150},
		{"label": _("Assigned To"), "fieldname": "assign_to", "fieldtype": "Link", "options": "User", "width": 150},
	]


def get_data(filters):
	conditions, values = [], []
	conditions.append(drafts_clause(filters, alias="am"))
	if filters.get("company"):
		conditions.append("am.company = %s")
		values.append(filters.company)
	if filters.get("maintenance_team"):
		conditions.append("am.maintenance_team = %s")
		values.append(filters.maintenance_team)
	if filters.get("assign_to"):
		conditions.append("amt.assign_to = %s")
		values.append(filters.assign_to)
	if filters.get("maintenance_status") and filters.maintenance_status in MAINTENANCE_TASK_STATUSES:
		conditions.append("amt.maintenance_status = %s")
		values.append(filters.maintenance_status)
	if filters.get("asset"):
		conditions.append("am.asset_name = %s")
		values.append(filters.asset)
	conditions.append("amt.next_due_date BETWEEN %s AND %s")
	values += [filters.due_from, filters.due_to]

	rows = frappe.db.sql(
		f"""
		select am.name as maintenance, am.asset_name as asset,
		       am.docstatus, a.asset_name as asset_display,
		       a.asset_category, amt.maintenance_task, amt.maintenance_type,
		       amt.periodicity, amt.maintenance_status, amt.next_due_date,
		       amt.last_completion_date, amt.assign_to, amt.start_date,
		       amt.end_date
		from `tabAsset Maintenance` am
		join `tabAsset Maintenance Task` amt on amt.parent = am.name
		join `tabAsset` a on a.name = am.asset_name
		WHERE {" AND ".join(conditions)}
		ORDER BY amt.next_due_date ASC, am.asset_name ASC
		""",
		values,
		as_dict=1,
	)

	today = getdate(nowdate())
	data = []
	by_status = frappe._dict()
	overdue = 0

	for r in rows:
		days = 0
		if r.next_due_date:
			days = (getdate(r.next_due_date) - today).days
		if days < 0 and r.maintenance_status != "Cancelled":
			overdue += 1

		data.append(frappe._dict(
			asset=r.asset,
			asset_name=r.asset_display or "",
			asset_category=r.asset_category,
			maintenance_task=r.maintenance_task,
			maintenance_type=r.maintenance_type,
			periodicity=r.periodicity,
			maintenance_status=_(r.maintenance_status) if r.maintenance_status else "",
			next_due_date=r.next_due_date,
			days_until_due=days,
			last_completion_date=r.last_completion_date,
			assign_to=r.assign_to,
		))
		by_status[r.maintenance_status or "-"] = by_status.get(r.maintenance_status or "-", 0) + 1

	message = "{t}: <b>{tc}</b> — {o}: <b>{oc}</b>".format(
		t=_("Maintenance Tasks"), tc=len(data),
		o=_("Overdue"), oc=overdue,
	)

	chart = get_chart(by_status)
	return data, message, chart


def get_chart(by_status):
	if not by_status:
		return {}
	items = sorted(by_status.items())
	return {
		"data": {
			"labels": [_(k) if k != "-" else _("Not Specified") for k, _cnt in items],
			"datasets": [{"name": _("Maintenance Tasks"), "values": [v for _k, v in items]}],
		},
		"type": "donut",
	}
