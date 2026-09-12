# Copyright (c) 2026, Asset Insights Team
# License: MIT
# Asset Movement Register — سجل حركة الأصول والعهدة
# Real v15 tables: `tabAsset Movement` (am) + `tabAsset Movement Item`
# (ami: asset, source_location, target_location, from_employee, to_employee).
# Purpose filter applies to posted AND draft rows alike; drafts only when
# Include Drafts is ticked. Detailed / Summary toggle.

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, get_datetime, nowdate, add_months

from asset_insights.asset_insights.utils import (
	drafts_clause,
	ASSET_MOVEMENT_PURPOSES,
)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	# sane defaults so the report always renders
	filters.from_date = filters.get("from_date") or add_months(getdate(nowdate()), -3)
	filters.to_date = filters.get("to_date") or nowdate()

	columns = get_columns(filters.get("view_type") or "Detailed")
	data, message, chart = get_data(filters)
	return columns, data, message, chart


def get_columns(view_type):
	if view_type == "Summary":
		return [
			{"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 110},
			{"label": _("Purpose"), "fieldname": "purpose", "fieldtype": "Data", "width": 130},
			{"label": _("Reference"), "fieldname": "reference", "fieldtype": "Data", "width": 170},
			{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
			{"label": _("Lines"), "fieldname": "lines", "fieldtype": "Int", "width": 70},
		]

	return [
		{"label": _("Date"), "fieldname": "date", "fieldtype": "Datetime", "width": 130},
		{"label": _("Movement ID"), "fieldname": "movement", "fieldtype": "Link", "options": "Asset Movement", "width": 150},
		{"label": _("Purpose"), "fieldname": "purpose", "fieldtype": "Data", "width": 130},
		{"label": _("Asset ID"), "fieldname": "asset", "fieldtype": "Link", "options": "Asset", "width": 150},
		{"label": _("Asset Name"), "fieldname": "asset_name", "fieldtype": "Data", "width": 180},
		{"label": _("From Location"), "fieldname": "source_location", "fieldtype": "Link", "options": "Location", "width": 140},
		{"label": _("To Location"), "fieldname": "target_location", "fieldtype": "Link", "options": "Location", "width": 140},
		{"label": _("From Custodian"), "fieldname": "from_employee", "fieldtype": "Link", "options": "Employee", "width": 130},
		{"label": _("To Custodian"), "fieldname": "to_employee", "fieldtype": "Link", "options": "Employee", "width": 130},
		{"label": _("Reference"), "fieldname": "reference", "fieldtype": "Data", "width": 170},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
	]


def get_data(filters):
	conditions, values = [], []
	conditions.append(drafts_clause(filters, alias="am"))
	if filters.get("company"):
		conditions.append("am.company = %s")
		values.append(filters.company)
	if filters.get("purpose") and filters.purpose in ASSET_MOVEMENT_PURPOSES:
		conditions.append("am.purpose = %s")
		values.append(filters.purpose)
	if filters.get("asset"):
		conditions.append("ami.asset = %s")
		values.append(filters.asset)
	conditions.append("am.transaction_date BETWEEN %s AND %s")
	values += [filters.from_date, filters.to_date]

	rows = frappe.db.sql(
		f"""
		select am.name as movement, am.purpose, am.transaction_date,
		       am.reference_doctype, am.reference_name, am.docstatus,
		       ami.asset, ami.asset_name, ami.source_location,
		       ami.target_location, ami.from_employee, ami.to_employee
		from `tabAsset Movement` am
		join `tabAsset Movement Item` ami on ami.parent = am.name
		WHERE {" AND ".join(conditions)}
		ORDER BY am.transaction_date ASC, am.name ASC
		""",
		values,
		as_dict=1,
	)

	data = []
	by_purpose = frappe._dict()
	groups = frappe._dict()
	gorder = []

	for r in rows:
		status = _("Draft") if r.docstatus == 0 else _("Submitted")
		reference = f"{r.reference_doctype or ''}: {r.reference_name or ''}".strip(": ")
		data.append(frappe._dict(
			date=r.transaction_date,
			movement=r.movement,
			purpose=_(r.purpose) if r.purpose else "",
			asset=r.asset,
			asset_name=r.asset_name,
			source_location=r.source_location,
			target_location=r.target_location,
			from_employee=r.from_employee,
			to_employee=r.to_employee,
			reference=reference,
			status=status,
		))
		by_purpose[r.purpose or "-"] = by_purpose.get(r.purpose or "-", 0) + 1

		gkey = (getdate(r.transaction_date), r.purpose or "", reference,
		        _("Draft") if r.docstatus == 0 else _("Submitted"))
		g = groups.get(gkey)
		if g is None:
			g = groups[gkey] = frappe._dict(
				date=gkey[0], purpose=_(r.purpose or ""), reference=reference,
				status=gkey[3], lines=0)
			gorder.append(gkey)
		g.lines += 1

	if (filters.get("view_type") or "Detailed") == "Summary":
		data = [groups[k] for k in gorder]

	message = "{t}: <b>{tc}</b> — {d}: <b>{dc}</b>".format(
		t=_("Movement Lines"), tc=len(data),
		d=_("Draft"), dc=sum(1 for d in data if d.status == _("Draft")),
	)

	chart = get_chart(by_purpose)
	return data, message, chart


def get_chart(by_purpose):
	if not by_purpose:
		return {}
	items = sorted(by_purpose.items())
	return {
		"data": {
			"labels": [_(k) for k, _cnt in items],
			"datasets": [{"name": _("Movement Lines"), "values": [v for _k, v in items]}],
		},
		"type": "donut",
	}
