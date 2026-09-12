# Copyright (c) 2026, Asset Insights Team
# License: MIT
# Maintenance Log Register — سجل أعمال الصيانة
# Real v15 tables: `tabAsset Maintenance Log` (ml) joined through
# `tabAsset Maintenance` (am) to `tabAsset` (a).
# Drafts only when Include Drafts is ticked.

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate, add_months

from asset_insights.asset_insights.utils import (
	drafts_clause,
	MAINTENANCE_LOG_STATUSES,
)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	filters.from_date = filters.get("from_date") or add_months(getdate(nowdate()), -3)
	filters.to_date = filters.get("to_date") or nowdate()

	columns = get_columns()
	data, message, chart = get_data(filters)
	return columns, data, message, chart


def get_columns():
	return [
		{"label": _("Due Date"), "fieldname": "due_date", "fieldtype": "Date", "width": 110},
		{"label": _("Log ID"), "fieldname": "name", "fieldtype": "Link", "options": "Asset Maintenance Log", "width": 150},
		{"label": _("Asset ID"), "fieldname": "asset", "fieldtype": "Link", "options": "Asset", "width": 150},
		{"label": _("Asset Name"), "fieldname": "asset_display", "fieldtype": "Data", "width": 170},
		{"label": _("Task"), "fieldname": "task_name", "fieldtype": "Data", "width": 180},
		{"label": _("Maintenance Type"), "fieldname": "maintenance_type", "fieldtype": "Data", "width": 130},
		{"label": _("Periodicity"), "fieldname": "periodicity", "fieldtype": "Data", "width": 100},
		{"label": _("Maintenance Status"), "fieldname": "maintenance_status", "fieldtype": "Data", "width": 130},
		{"label": _("Completion Date"), "fieldname": "completion_date", "fieldtype": "Date", "width": 130},
		{"label": _("Performed By"), "fieldname": "assign_to_name", "fieldtype": "Data", "width": 150},
		{"label": _("Actions Performed"), "fieldname": "actions_performed", "fieldtype": "Small Text", "width": 250},
	]


def get_data(filters):
	conditions, values = [], []
	conditions.append(drafts_clause(filters, alias="ml"))
	if filters.get("company"):
		conditions.append("am.company = %s")
		values.append(filters.company)
	if filters.get("asset"):
		conditions.append("am.asset_name = %s")
		values.append(filters.asset)
	if filters.get("maintenance_status") and filters.maintenance_status in MAINTENANCE_LOG_STATUSES:
		conditions.append("ml.maintenance_status = %s")
		values.append(filters.maintenance_status)
	conditions.append("ml.due_date BETWEEN %s AND %s")
	values += [filters.from_date, filters.to_date]

	rows = frappe.db.sql(
		f"""
		select ml.name, ml.asset_maintenance, ml.task_name,
		       ml.maintenance_type, ml.periodicity, ml.maintenance_status,
		       ml.due_date, ml.completion_date, ml.assign_to_name,
		       ml.actions_performed, ml.docstatus,
		       am.asset_name as asset, a.asset_name as asset_display
		from `tabAsset Maintenance Log` ml
		join `tabAsset Maintenance` am on am.name = ml.asset_maintenance
		join `tabAsset` a on a.name = am.asset_name
		WHERE {" AND ".join(conditions)}
		ORDER BY ml.due_date ASC, ml.name ASC
		""",
		values,
		as_dict=1,
	)

	data = []
	by_status = frappe._dict()
	completed = 0

	for r in rows:
		status = _("Draft") if r.docstatus == 0 else (_(r.maintenance_status) if r.maintenance_status else "")
		if r.maintenance_status == "Completed":
			completed += 1
		data.append(frappe._dict(
			name=r.name,
			due_date=r.due_date,
			asset=r.asset,
			asset_display=r.asset_display or "",
			task_name=r.task_name or "",
			maintenance_type=r.maintenance_type,
			periodicity=r.periodicity,
			maintenance_status=status,
			completion_date=r.completion_date,
			assign_to_name=r.assign_to_name or "",
			actions_performed=(r.actions_performed or "")[:280],
		))
		by_status[status or "-"] = by_status.get(status or "-", 0) + 1

	rate = flt(completed * 100.0 / len(rows), 1) if rows else 0.0
	message = "{t}: <b>{tc}</b> — {r}: <b>{rt}%</b>".format(
		t=_("Maintenance Logs"), tc=len(data),
		r=_("Completion Rate"), rt=rate,
	)

	chart = get_chart(by_status)
	return data, message, chart


def get_chart(by_status):
	if not by_status:
		return {}
	items = sorted(by_status.items())
	return {
		"data": {
			"labels": [k if k != "-" else _("Not Specified") for k, _cnt in items],
			"datasets": [{"name": _("Maintenance Logs"), "values": [v for _k, v in items]}],
		},
		"type": "donut",
	}
