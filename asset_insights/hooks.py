# Copyright (c) 2026, Asset Insights Team
# License: MIT

app_name = "asset_insights"
app_title = "Asset Insights"
app_publisher = "Asset Insights Team"
app_description = (
	"Professional BI reports & dashboards for ERPNext v15 — Fixed Assets. "
	"(تقارير وداشبوردات احترافية للأصول الثابتة)"
)
app_email = "bi@example.com"
app_license = "mit"
# required_apps = ["frappe/erpnext"]

# Runs after every `bench migrate`: creates public Number Cards and
# Dashboard Charts. The public Workspace itself ships as a STANDARD
# Workspace JSON (auto-synced by frappe), see:
#   asset_insights/asset_insights/workspace/asset_insights/asset_insights.json
after_migrate = ["asset_insights.install.after_migrate"]
