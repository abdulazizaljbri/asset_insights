# Copyright (c) 2026, Asset Insights Team
# License: MIT
# Asset Movement Register — سجل حركة الأصول والعهدة (v15.23.1-verified)
# Two complementary sources:
#   1) real `tabAsset Movement` documents (+ their items);
#   2) synthesized "Custody Assignment" rows straight from `tabAsset` for
#      assets that HAVE a custodian but NO Asset Movement document yet —
#      so a hand-entered asset (even a draft) always shows its custody.
# Draft documents appear only when Include Drafts is ticked. The Purpose
# filter applies to posted AND draft/synthesized rows alike.
# Detailed / Summary toggle.

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate, add_months

from asset_insights.asset_insights.utils import (
	drafts_clause,
	ASSET_MOVEMENT_PURPOSES,
)

CUSTODY_LABEL = "Custody Assignment"


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
			{"label": _("Purpose"), "fieldname": "purpose", "fieldtype": "Data", "width": 140},
			{"label": _("Voucher No"), "fieldname": "voucher_no", "fieldtype": "Dynamic Link", "options": "voucher_type", "width": 160},
			{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
			{"label": _("Lines"), "fieldname": "lines", "fieldtype": "Int", "width": 70},
		]

	return [
		{"label": _("Date"), "fieldname": "date", "fieldtype": "Datetime", "width": 130},
		{"label": _("Voucher Type"), "fieldname": "voucher_type", "fieldtype": "Data", "width": 120},
		{"label": _("Voucher No"), "fieldname": "voucher_no", "fieldtype": "Dynamic Link", "options": "voucher_type", "width": 160},
		{"label": _("Purpose"), "fieldname": "purpose", "fieldtype": "Data", "width": 140},
		{"label": _("Asset ID"), "fieldname": "asset", "fieldtype": "Link", "options": "Asset", "width": 150},
		{"label": _("Asset Name"), "fieldname": "asset_name", "fieldtype": "Data", "width": 180},
		{"label": _("From Location"), "fieldname": "source_location", "fieldtype": "Link", "options": "Location", "width": 140},
		{"label": _("To Location"), "fieldname": "target_location", "fieldtype": "Link", "options": "Location", "width": 140},
		{"label": _("From Custodian"), "fieldname": "from_employee", "fieldtype": "Link", "options": "Employee", "width": 130},
		{"label": _("To Custodian"), "fieldname": "to_employee", "fieldtype": "Link", "options": "Employee", "width": 130},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
	]


def get_movement_rows(filters):
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

	return frappe.db.sql(
		f"""
		select 'Asset Movement' as voucher_type,
		       am.name as voucher_no, am.purpose, am.transaction_date,
		       am.docstatus,
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


def get_custody_rows(filters):
	"""Assets holding a custodian without any Asset Movement document.

	Covers hand-entered assets (draft or submitted): their initial custody
	assignment shows here so the register is never blind to them. The
	Purpose filter treats custody like a Receipt.
	"""
	purpose = filters.get("purpose")
	if purpose and purpose not in ("", "Receipt"):
		return []

	conditions, values = [], []
	conditions.append(drafts_clause(filters, alias="a"))
	conditions.append("(a.custodian is not null and a.custodian != '')")
	conditions.append(
		"not exists (select 1 from `tabAsset Movement Item` x where x.asset = a.name)"
	)
	if filters.get("company"):
		conditions.append("a.company = %s")
		values.append(filters.company)
	if filters.get("asset"):
		conditions.append("a.name = %s")
		values.append(filters.asset)
	conditions.append(
		"coalesce(a.available_for_use_date, a.purchase_date, date(a.creation)) BETWEEN %s AND %s"
	)
	values += [filters.from_date, filters.to_date]

	return frappe.db.sql(
		f"""
		select 'Asset' as voucher_type,
		       a.name as voucher_no,
		       'Custody Assignment' as purpose,
		       coalesce(a.available_for_use_date, a.purchase_date,
		                date(a.creation)) as transaction_date,
		       a.docstatus,
		       a.name as asset, a.asset_name,
		       null as source_location,
		       a.location as target_location,
		       null as from_employee,
		       a.custodian as to_employee
		from `tabAsset` a
		WHERE {" AND ".join(conditions)}
		ORDER BY transaction_date ASC, a.name ASC
		""",
		values,
		as_dict=1,
	)


def get_data(filters):
	rows = list(get_movement_rows(filters)) + list(get_custody_rows(filters))
	rows.sort(key=lambda r: (getdate(r.transaction_date or "1970-01-01"),
	                         str(r.voucher_no)))

	data = []
	by_purpose = frappe._dict()
	groups = frappe._dict()
	gorder = []

	for r in rows:
		status = _("Draft") if r.docstatus == 0 else _("Submitted")
		purpose_display = _(r.purpose) if r.purpose else ""

		data.append(frappe._dict(
			date=r.transaction_date,
			voucher_type=r.voucher_type,
			voucher_no=r.voucher_no,
			purpose=purpose_display,
			asset=r.asset,
			asset_name=r.asset_name,
			source_location=r.source_location,
			target_location=r.target_location,
			from_employee=r.from_employee,
			to_employee=r.to_employee,
			status=status,
		))
		by_purpose[purpose_display or "-"] = by_purpose.get(purpose_display or "-", 0) + 1

		gkey = (getdate(r.transaction_date or "1970-01-01"), purpose_display,
		        r.voucher_type, r.voucher_no, status)
		g = groups.get(gkey)
		if g is None:
			g = groups[gkey] = frappe._dict(
				date=gkey[0], purpose=purpose_display,
				voucher_type=r.voucher_type, voucher_no=r.voucher_no,
				status=status, lines=0)
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
			"labels": [k for k, _cnt in items],
			"datasets": [{"name": _("Movement Lines"),
			              "values": [_cnt for _k, _cnt in items]}],
		},
		"type": "donut",
	}
