# Copyright (c) 2026, Asset Insights Team
# License: MIT
# Asset Value Summary — ملخص قيم الأصول
# Aggregates gross / accumulated depreciation / NBV by a chosen dimension
# (Asset Category, Location, Custodian or Company). Drafts only when
# Include Drafts is ticked.

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

from asset_insights.asset_insights.utils import (
	build_asset_conditions,
	currency_fmt,
	drafts_clause,
	get_company_currency,
)

GROUP_BY = {
	"Asset Category": "a.asset_category",
	"Location": "a.location",
	"Custodian": "coalesce(e.employee_name, a.custodian)",
	"Company": "a.company",
}


def execute(filters=None):
	filters = frappe._dict(filters or {})
	filters.as_of = filters.get("as_of") or nowdate()
	filters.group_by = filters.get("group_by") or "Asset Category"

	columns = get_columns(filters.group_by)
	data, message, chart = get_data(filters)
	return columns, data, message, chart


def get_columns(group_by):
	label = {
		"Asset Category": _("Asset Category"),
		"Location": _("Location"),
		"Custodian": _("Custodian"),
		"Company": _("Company"),
	}[group_by]
	fieldtype = {"Asset Category": "Link", "Location": "Link", "Company": "Link"}.get(
		group_by, "Data"
	)
	options = group_by if fieldtype == "Link" else None

	cols = [
		{"label": label, "fieldname": "group_value",
		 "fieldtype": fieldtype, "width": 220},
	]
	if options:
		cols[0]["options"] = options

	cols += [
		{"label": _("Count"), "fieldname": "asset_count", "fieldtype": "Int", "width": 80},
		{"label": _("Gross Purchase Amount"), "fieldname": "gross", "fieldtype": "Currency", "width": 160},
		{"label": _("Accumulated Depreciation"), "fieldname": "accum_dep", "fieldtype": "Currency", "width": 170},
		{"label": _("Net Book Value"), "fieldname": "nbv", "fieldtype": "Currency", "width": 160},
		{"label": _("% of NBV"), "fieldname": "nbv_pct", "fieldtype": "Percent", "width": 100},
	]
	return cols


def get_data(filters):
	dimension = GROUP_BY.get(filters.group_by) or GROUP_BY["Asset Category"]
	conditions, values = build_asset_conditions(filters)
	conditions.append(drafts_clause(filters))
	conditions.append("a.status != 'Cancelled'")
	conditions.append("(a.purchase_date is null or a.purchase_date <= %s)")
	values.append(filters.as_of)

	rows = frappe.db.sql(
		f"""
		select {dimension} as group_value,
		       a.gross_purchase_amount as gross,
		       a.value_after_depreciation as nbv,
		       a.status
		from `tabAsset` a
		left join `tabEmployee` e on e.name = a.custodian
		WHERE {" AND ".join(conditions)}
		""",
		values,
		as_dict=1,
	)

	groups = frappe._dict()
	order = []
	total = frappe._dict(asset_count=0, gross=0.0, accum_dep=0.0, nbv=0.0)

	for r in rows:
		key = r.group_value or _("Not Specified")
		g = groups.setdefault(key, frappe._dict(
			group_value=key, asset_count=0, gross=0.0, accum_dep=0.0, nbv=0.0))
		if key not in order:
			order.append(key)

		gross = flt(r.gross)
		nbv = flt(r.nbv) if flt(r.nbv) else gross
		accum = max(gross - nbv, 0.0)

		g.asset_count += 1
		g.gross += gross
		g.accum_dep += accum
		g.nbv += nbv
		total.asset_count += 1
		total.gross += gross
		total.accum_dep += accum
		total.nbv += nbv

	data = [groups[k] for k in sorted(order)]
	for d in data:
		d.nbv_pct = flt(d.nbv * 100.0 / total.nbv, 1) if total.nbv else 0.0

	currency = get_company_currency(filters.get("company"))
	message = "{c}: <b>{cnt}</b> — {g}: <b>{gv}</b> — {n}: <b>{nv}</b>".format(
		c=_("Assets"), cnt=total.asset_count,
		g=_("Gross Purchase Amount"), gv=currency_fmt(total.gross, currency),
		n=_("Net Book Value"), nv=currency_fmt(total.nbv, currency),
	)

	chart = get_chart(data)
	return data, message, chart


def get_chart(data):
	if not data:
		return {}
	top = sorted(data, key=lambda x: x.nbv, reverse=True)[:10]
	return {
		"data": {
			"labels": [str(d.group_value) for d in top],
			"datasets": [{"name": _("Net Book Value"), "values": [flt(d.nbv) for d in top]}],
		},
		"type": "bar",
	}
