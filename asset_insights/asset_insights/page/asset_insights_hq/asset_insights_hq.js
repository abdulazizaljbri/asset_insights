/* Asset Insights HQ — executive asset dashboard for ERPNext v15.
   Runs the Asset Insights script reports server-side and renders live
   KPIs + charts with the bundled frappe-charts library. */

frappe.pages["asset-insights-hq"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Asset Insights HQ"),
		single_column: true,
	});

	const company_field = page.add_field({
		fieldname: "company",
		label: __("Company"),
		fieldtype: "Link",
		options: "Company",
		default: frappe.defaults.get_user_default("Company"),
		change() {
			load();
		},
	});

	const drafts_field = page.add_field({
		fieldname: "include_drafts",
		label: __("Include Drafts"),
		fieldtype: "Check",
		default: 1,
		change() {
			load();
		},
	});

	page.set_primary_action(__("Refresh"), () => load());
	page.set_secondary_action(__("Workspace"), () =>
		frappe.set_route("app/asset-insights")
	);

	wrapper.querySelector(".layout-main-section-wrapper").classList.add("ai-hq-wrapper");
	const main = wrapper.querySelector(".layout-main-section");

	const KPI_SLOTS = [
		["kpi-assets", __("Total Assets"), "#2490ef"],
		["kpi-nbv", __("Net Book Value"), "#29cd42"],
		["kpi-dep", __("Depreciation (12m)"), "#813bff"],
		["kpi-overdue", __("Overdue Maintenance"), "#f59f00"],
		["kpi-repairs", __("Pending Repairs"), "#e42137"],
		["kpi-moves", __("Movements (30d)"), "#ec8d30"],
	];

	main.innerHTML = `
		<div class="ai-hq">
			<div class="ai-kpis">
				${KPI_SLOTS.map(
					([id, label, color]) => `
					<div class="ai-kpi" style="--kc:${color}">
						<div class="ai-kpi-label">${label}</div>
						<div class="ai-kpi-value" id="${id}">…</div>
						<div class="ai-kpi-sub" id="${id}-sub"></div>
					</div>`
				).join("")}
			</div>
			<div class="ai-charts">
				<div class="ai-chart-card">
					<div class="ai-chart-title">${__("Net Book Value by Category")}</div>
					<div id="ai-c1"></div>
				</div>
				<div class="ai-chart-card">
					<div class="ai-chart-title">${__("Depreciation (Monthly)")}</div>
					<div id="ai-c2"></div>
				</div>
				<div class="ai-chart-card">
					<div class="ai-chart-title">${__("Repair Cost (Monthly)")}</div>
					<div id="ai-c3"></div>
				</div>
				<div class="ai-chart-card">
					<div class="ai-chart-title">${__("Movements by Purpose")}</div>
					<div id="ai-c4"></div>
				</div>
			</div>
		</div>`;

	let currency = null;

	function set_kpi(id, value, sub) {
		const el = document.getElementById(id);
		if (el) el.innerHTML = value;
		const sub_el = document.getElementById(id + "-sub");
		if (sub_el) sub_el.innerHTML = sub || "";
	}

	function fmt_money(value, precision = 0) {
		try {
			return format_currency(value || 0, currency || undefined, precision);
		} catch (e) {
			return (value || 0).toLocaleString();
		}
	}

	function empty(id) {
		const el = document.getElementById(id);
		if (el) el.innerHTML = `<div class="ai-empty">${__("No data for the selected filters")}</div>`;
	}

	function render_chart(id, type, labels, datasets, colors, y_currency) {
		const el = document.getElementById(id);
		if (!el) return;
		if (!labels || !labels.length) return empty(id);
		el.innerHTML = "";
		new frappe.Chart(el, {
			type: type,
			colors: colors,
			height: 240,
			axisOptions: { xIsSeries: type === "line", shortenYAxisNumbers: 1 },
			data: { labels: labels, datasets: datasets },
			tooltipOptions: {
				formatTooltipY: (v) => (y_currency ? fmt_money(v, 0) : String(v)),
			},
		});
	}

	function run(report_name, filters) {
		return frappe
			.call({
				method: "frappe.desk.query_report.run",
				args: {
					report_name: report_name,
					filters: Object.assign(
						{
							company: company_field.get_value() || undefined,
							include_drafts: drafts_field.get_value() ? 1 : 0,
						},
						filters || {}
					),
				},
			})
			.then((r) => (r.message && r.message.result) || []);
	}

	function load() {
		const today = frappe.datetime.get_today();
		const in_12m = frappe.datetime.add_months(today, 12);
		const month_ago = frappe.datetime.add_months(today, -1);

		KPI_SLOTS.forEach(([id]) => set_kpi(id, "…", ""));

		run("ai_asset_value_summary", { group_by: "Asset Category", as_of: today })
			.then((rows) => {
				const total_nbv = rows.reduce((a, x) => a + (x.nbv || 0), 0);
				const total_gross = rows.reduce((a, x) => a + (x.gross || 0), 0);
				const count = rows.reduce((a, x) => a + (x.asset_count || 0), 0);
				currency = currency || null;
				set_kpi("kpi-assets", String(count), `${fmt_money(total_gross)} ${__("gross")}`);
				set_kpi("kpi-nbv", fmt_money(total_nbv), `${rows.length} ${__("categories")}`);

				const cat_rows = rows.slice().sort((a, b) => (b.nbv || 0) - (a.nbv || 0)).slice(0, 10);
				render_chart("ai-c1", "bar", cat_rows.map((x) => x.group_value),
					[{ name: __("Net Book Value"), values: cat_rows.map((x) => Math.round(x.nbv || 0)) }],
					["#29cd42"], true);
			})
			.catch(() => empty("ai-c1"));

		run("ai_depreciation_plan", { from_date: today, to_date: in_12m })
			.then((rows) => {
				const total = rows.reduce((a, x) => a + (x.depreciation_amount || 0), 0);
				set_kpi("kpi-dep", fmt_money(total), `${rows.length} ${__("scheduled bookings")}`);
				const by_month = {};
				rows.forEach((x) => {
					if (!x.schedule_date) return;
					const k = x.schedule_date.slice(0, 7);
					by_month[k] = (by_month[k] || 0) + (x.depreciation_amount || 0);
				});
				const keys = Object.keys(by_month).sort();
				render_chart("ai-c2", "line", keys.map((k) => frappe.datetime.str_to_obj(k + "-15").toLocaleDateString(undefined, { month: "short", year: "2-digit" })),
					[{ name: __("Depreciation Amount"), values: keys.map((k) => Math.round(by_month[k])) }],
					["#813bff"], true);
			})
			.catch(() => empty("ai-c2"));

		run("ai_maintenance_schedule", { due_from: today, due_to: in_12m })
			.then((rows) => {
				const overdue = rows.filter((x) => (x.days_until_due || 0) < 0).length;
				set_kpi("kpi-overdue", String(overdue), `${rows.length} ${__("scheduled tasks")}`);
			})
			.catch(() => set_kpi("kpi-overdue", "—", ""));

		run("ai_repair_register", { from_date: month_ago, to_date: today })
			.then((rows) => {
				const pending = rows.filter((x) => x.repair_status === __("Pending")).length;
				const cost = rows.reduce((a, x) => a + (x.total_repair_cost || x.repair_cost || 0), 0);
				set_kpi("kpi-repairs", String(pending), `${fmt_money(cost)} ${__("this month")}`);

				const by_month = {};
				rows.forEach((x) => {
					if (!x.failure_date) return;
					const k = x.failure_date.slice(0, 7);
					by_month[k] = (by_month[k] || 0) + (x.total_repair_cost || x.repair_cost || 0);
				});
				const keys = Object.keys(by_month).sort().slice(-12);
				render_chart("ai-c3", "bar", keys.map((k) => frappe.datetime.str_to_obj(k + "-15").toLocaleDateString(undefined, { month: "short", year: "2-digit" })),
					[{ name: __("Total Repair Cost"), values: keys.map((k) => Math.round(by_month[k])) }],
					["#e42137"], true);
			})
			.catch(() => empty("ai-c3"));

		run("ai_asset_movement_register", { from_date: month_ago, to_date: today })
			.then((rows) => {
				set_kpi("kpi-moves", String(rows.length), __("last 30 days"));
				const by_purpose = {};
				rows.forEach((x) => {
					by_purpose[x.purpose || "—"] = (by_purpose[x.purpose || "—"] || 0) + 1;
				});
				const items = Object.entries(by_purpose);
				render_chart("ai-c4", "donut", items.map((x) => x[0]),
					[{ name: __("Movement Lines"), values: items.map((x) => x[1]) }],
					["#2490ef", "#29cd42", "#f59f00", "#813bff"], false);
			})
			.catch(() => empty("ai-c4"));
	}

	frappe.call({
		method: "frappe.client.get_value",
		args: { doctype: "Global Defaults", fieldname: "default_currency" },
		callback(r) {
			currency = (r.message && r.message.default_currency) || null;
		},
	});

	load();
};

frappe.pages["asset-insights-hq"].on_page_show = function () {
	// nothing extra yet
};
