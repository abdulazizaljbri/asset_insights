# Copyright (c) 2026, Asset Insights Team
# License: MIT
# Asset Repair Register — سجل إصلاحات الأصول
# Real v15 fields on `tabAsset Repair`: failure_date, completion_date,
# repair_status (Pending/Completed/Cancelled), repair_cost,
# total_repair_cost, capitalize_repair_cost, increase_in_asset_life, downtime.
# Drafts only when Include Drafts is ticked.

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate, add_months

from asset_insights.asset_insights.utils import (
	currency_fmt,
	drafts_clause,
	get_company_currency,
	REPAIR_STATUSES,
	month_key,
	month_label,
)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	filters.from_date = filters.get("from_date") or add_months(getdate(nowdate()), -6)
	filters.to_date = filters.get("to_date") or nowdate()

	columns = get_columns()
	data, message, chart = get_data(filters)
	return columns, data, message, chart


def get_columns():
	return [
		{"label": _("Failure Date"), "fieldname": "failure_date", "fieldtype": "Datetime", "width": 130},
		{"label": _("Repair ID"), "fieldname": "name", "fieldtype": "Link", "options": "Asset Repair", "width": 150},
		{"label": _("Asset ID"), "fieldname": "asset", "fieldtype": "Link", "options": "Asset", "width": 150},
		{"label": _("Asset Name"), "fieldname": "asset_name", "fieldtype": "Data", "width": 170},
		{"label": _("Repair Status"), "fieldname": "repair_status", "fieldtype": "Data", "width": 120},
		{"label": _("Completion Date"), "fieldname": "completion_date", "fieldtype": "Datetime", "width": 130},
		{"label": _("Downtime (days)"), "fieldname": "downtime", "fieldtype": "Data", "width": 110},
		{"label": _("Repair Cost"), "fieldname": "repair_cost", "fieldtype": "Currency", "width": 130},
		{"label": _("Total Repair Cost"), "fieldname": "total_repair_cost", "fieldtype": "Currency", "width": 150},
		{"label": _("Capitalize Repair Cost"), "fieldname": "capitalize_repair_cost", "fieldtype": "Check", "width": 140},
		{"label": _("Increase In Asset Life (days)"), "fieldname": "increase_in_asset_life", "fieldtype": "Int", "width": 170},
		{"label": _("Description"), "fieldname": "description", "fieldtype": "Small Text", "width": 250},
	]


def get_data(filters):
	conditions, values = [], []
	conditions.append(drafts_clause(filters, alias="ar"))
	if filters.get("company"):
		conditions.append("ar.company = %s")
		values.append(filters.company)
	if filters.get("asset"):
		conditions.append("ar.asset = %s")
		values.append(filters.asset)
	if filters.get("repair_status") and filters.repair_status in REPAIR_STATUSES:
		conditions.append("ar.repair_status = %s")
		values.append(filters.repair_status)
	conditions.append("ar.failure_date BETWEEN %s AND %s")
	values += [filters.from_date, filters.to_date]

	rows = frappe.db.sql(
		f"""
		select ar.name, ar.asset, ar.asset_name, ar.failure_date,
		       ar.completion_date, ar.repair_status, ar.downtime,
		       ar.repair_cost, ar.total_repair_cost,
		       ar.capitalize_repair_cost, ar.increase_in_asset_life,
		       ar.description, ar.docstatus
		from `tabAsset Repair` ar
		WHERE {" AND ".join(conditions)}
		ORDER BY ar.failure_date ASC, ar.name ASC
		""",
		values,
		as_dict=1,
	)

	currency = get_company_currency(filters.get("company"))
	data = []
	by_month = frappe._dict()
	total_cost = 0.0
	pending = 0

	for r in rows:
		cost = flt(r.total_repair_cost) if flt(r.total_repair_cost) else flt(r.repair_cost)
		status = _("Draft") if r.docstatus == 0 else (_(r.repair_status) if r.repair_status else "")
		if r.repair_status == "Pending":
			pending += 1

		data.append(frappe._dict(
			name=r.name,
			failure_date=r.failure_date,
			asset=r.asset,
			asset_name=r.asset_name or "",
			repair_status=status,
			completion_date=r.completion_date,
			downtime=r.downtime or "",
			repair_cost=flt(r.repair_cost),
			total_repair_cost=cost,
			capitalize_repair_cost=cint(r.capitalize_repair_cost),
			increase_in_asset_life=cint(r.increase_in_asset_life),
			description=(r.description or "")[:280],
		))
		total_cost += cost
		if r.failure_date:
			k = month_key(r.failure_date)
			by_month[k] = by_month.get(k, 0.0) + cost

	message = "{t}: <b>{tc}</b> — {c}: <b>{cv}</b> — {p}: <b>{pc}</b>".format(
		t=_("Repairs"), tc=len(data),
		c=_("Total Repair Cost"), cv=currency_fmt(total_cost, currency),
		p=_("Pending"), pc=pending,
	)

	chart = get_chart(by_month)
	return data, message, chart


def get_chart(by_month):
	if not by_month:
		return {}
	labels, vals = [], []
	for k in sorted(by_month):
		labels.append(month_label(f"{k}-15"))
		vals.append(flt(by_month[k]))
	return {
		"data": {
			"labels": labels,
			"datasets": [{"name": _("Total Repair Cost"), "values": vals}],
		},
		"type": "bar",
	}
