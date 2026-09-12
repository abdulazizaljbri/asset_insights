# Copyright (c) 2026, Asset Insights Team
# License: MIT
# Asset Ageing — أعمار الأصول
# Buckets owned assets by age since purchase_date, with gross / NBV per
# bucket. Drafts only when Include Drafts is ticked.

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

from asset_insights.asset_insights.utils import (
	build_asset_conditions,
	currency_fmt,
	drafts_clause,
	get_company_currency,
)

BUCKETS = [
	(0, 1, "0 - 1"),
	(1, 3, "1 - 3"),
	(3, 5, "3 - 5"),
	(5, 10, "5 - 10"),
	(10, None, "> 10"),
]


def execute(filters=None):
	filters = frappe._dict(filters or {})
	filters.as_of = filters.get("as_of") or nowdate()

	columns = get_columns()
	data, message, chart = get_data(filters)
	return columns, data, message, chart


def get_columns():
	return [
		{"label": _("Age Bucket (Years)"), "fieldname": "bucket", "fieldtype": "Data", "width": 150},
		{"label": _("Count"), "fieldname": "asset_count", "fieldtype": "Int", "width": 80},
		{"label": _("Gross Purchase Amount"), "fieldname": "gross", "fieldtype": "Currency", "width": 160},
		{"label": _("Accumulated Depreciation"), "fieldname": "accum_dep", "fieldtype": "Currency", "width": 170},
		{"label": _("Net Book Value"), "fieldname": "nbv", "fieldtype": "Currency", "width": 160},
		{"label": _("Average Age (Years)"), "fieldname": "avg_age", "fieldtype": "Float", "width": 140},
		{"label": _("% of NBV"), "fieldname": "nbv_pct", "fieldtype": "Percent", "width": 100},
	]


def _bucket_of(age_years):
	for lo, hi, label in BUCKETS:
		if age_years >= lo and (hi is None or age_years < hi):
			return label
	return BUCKETS[-1][2]


def get_data(filters):
	conditions, values = build_asset_conditions(filters)
	conditions.append(drafts_clause(filters))
	conditions.append("a.status != 'Cancelled'")
	conditions.append("(a.purchase_date is null or a.purchase_date <= %s)")
	values.append(filters.as_of)

	rows = frappe.db.sql(
		f"""
		select a.purchase_date, a.gross_purchase_amount,
		       a.value_after_depreciation
		from `tabAsset` a
		WHERE {" AND ".join(conditions)}
		""",
		values,
		as_dict=1,
	)

	as_of = getdate(filters.as_of)
	order = [b[2] for b in BUCKETS]
	groups = frappe._dict()
	total_nbv = 0.0

	for r in rows:
		age = 0.0
		if r.purchase_date:
			age = max((as_of - getdate(r.purchase_date)).days / 365.0, 0.0)
		label = _bucket_of(age)
		g = groups.get(label)
		if g is None:
			g = groups[label] = frappe._dict(
				bucket=label, asset_count=0, gross=0.0,
				accum_dep=0.0, nbv=0.0, age_sum=0.0)
		gross = flt(r.gross_purchase_amount)
		nbv = flt(r.value_after_depreciation) if flt(r.value_after_depreciation) else gross
		g.asset_count += 1
		g.gross += gross
		g.accum_dep += max(gross - nbv, 0.0)
		g.nbv += nbv
		g.age_sum += age
		total_nbv += nbv

	data = []
	for label in order:
		g = groups.get(label)
		if not g:
			continue
		g.avg_age = flt(g.age_sum / g.asset_count, 1)
		g.nbv_pct = flt(g.nbv * 100.0 / total_nbv, 1) if total_nbv else 0.0
		data.append(g)

	currency = get_company_currency(filters.get("company"))
	message = "{c}: <b>{cnt}</b> — {n}: <b>{nv}</b>".format(
		c=_("Assets"), cnt=sum(d.asset_count for d in data),
		n=_("Net Book Value"), nv=currency_fmt(total_nbv, currency),
	)

	chart = get_chart(data)
	return data, message, chart


def get_chart(data):
	if not data:
		return {}
	return {
		"data": {
			"labels": [d.bucket for d in data],
			"datasets": [
				{"name": _("Net Book Value"), "values": [flt(d.nbv) for d in data]},
			],
		},
		"type": "bar",
	}
