/* Asset Finance HQ — depreciation & value dashboard (clean rebuild v8).
 * ERPNext v15 — verified APIs only (see asset_insights_hq.js header).
 * Plain in-body controls; drafts included by default. */

frappe.pages["asset-finance-hq"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Asset Finance HQ"),
		single_column: true,
	});

	page.set_primary_action(__("Refresh"), () => load());
	page.set_secondary_action(__("Workspace"), () =>
		frappe.set_route("app/asset-insights")
	);

	const kpis = () => [
		["kpi-gross", __("Gross Value"), "#2490ef"],
		["kpi-accum", __("Accumulated Depreciation"), "#f59f00"],
		["kpi-nbv", __("Net Book Value"), "#29cd42"],
		["kpi-age", __("Average Age"), "#813bff"],
		["kpi-eol", __("Nearing End Of Life"), "#e42137"],
		["kpi-disposed", __("Disposals (12m)"), "#ec8d30"],
	];

	const chartCard = (id, title) => `
		<div class="ai-chart-card">
			<div class="ai-chart-title">${title}</div>
			<div id="${id}"></div>
		</div>`;

	const main = wrapper.querySelector(".layout-main-section");
	main.innerHTML = `
		<div class="ai-hq">
			<div class="ai-controls">
				<div class="ai-control">
					<div class="ai-control-label">${__("Company")}</div>
					<select id="ai-company" class="form-control"></select>
				</div>
				<label class="ai-control ai-switch">
					<input type="checkbox" id="ai-drafts" checked>
					<span>${__("Include Drafts")}</span>
				</label>
			</div>
			<div id="ai-fhint" class="ai-hint" style="display:none"></div>
			<div class="ai-kpis">
				${kpis()
					.map(
						([id, label, color]) => `
					<div class="ai-kpi" style="--kc:${color}">
						<div class="ai-kpi-label">${label}</div>
						<div class="ai-kpi-value" id="${id}">…</div>
						<div class="ai-kpi-sub" id="${id}-sub"></div>
					</div>`
					)
					.join("")}
			</div>
			<div class="ai-charts">
				${chartCard("ai-f1", __("Net Book Value by Location"))}
				${chartCard("ai-f2", __("Asset Ageing"))}
				${chartCard("ai-f3", __("Disposal NBV (Monthly)"))}
				${chartCard("ai-f4", __("Assets Nearing End Of Life"))}
			</div>
			<div class="ai-version">Asset Finance HQ • v8</div>
		</div>`;

	let currency = null;
	const company_select = document.getElementById("ai-company");
	const drafts_box = document.getElementById("ai-drafts");

	function fmt_money(value, precision = 0) {
		try {
			return format_currency(value || 0, currency || undefined, precision);
		} catch (e) {
			return (value || 0).toLocaleString();
		}
	}

	function set_kpi(id, value, sub) {
		const v = document.getElementById(id);
		if (v) v.innerHTML = value;
		const s = document.getElementById(id + "-sub");
		if (s) s.innerHTML = sub || "";
	}

	function empty_chart(id) {
		const el = document.getElementById(id);
		if (el)
			el.innerHTML = `<div class="ai-empty">${__(
				"No data for the selected filters"
			)}</div>`;
	}

	function draw(id, type, labels, datasets, colors, money) {
		const el = document.getElementById(id);
		if (!el) return;
		if (!labels || !labels.length) return empty_chart(id);
		el.innerHTML = "";
		new frappe.Chart(el, {
			type: type,
			colors: colors,
			height: 240,
			axisOptions: { xIsSeries: type === "line", shortenYAxisNumbers: 1 },
			data: { labels: labels, datasets: datasets },
			tooltipOptions: {
				formatTooltipY: (v) => (money ? fmt_money(v, 0) : String(v)),
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
							company: company_select.value || undefined,
							include_drafts: drafts_box.checked ? 1 : 0,
						},
						filters || {}
					),
				},
			})
			.then((r) => (r.message && r.message.result) || []);
	}

	function month_label(ym) {
		return frappe.datetime
			.str_to_obj(ym + "-15")
			.toLocaleDateString(undefined, { month: "short", year: "2-digit" });
	}

	function by_month(rows, date_field, value_field) {
		const out = {};
		rows.forEach((x) => {
			const d = x[date_field];
			if (!d) return;
			const k = String(d).slice(0, 7);
			out[k] = (out[k] || 0) + (x[value_field] || 0);
		});
		return out;
	}

	function load() {
		const today = frappe.datetime.get_today();
		const year_ago = frappe.datetime.add_months(today, -12);
		kpis().forEach(([id]) => set_kpi(id, "…", ""));

		run("ai_asset_value_summary", { group_by: "Company", as_of: today })
			.then((rows) => {
				const gross = rows.reduce((a, x) => a + (x.gross || 0), 0);
				const accum = rows.reduce((a, x) => a + (x.accum_dep || 0), 0);
				const nbv = rows.reduce((a, x) => a + (x.nbv || 0), 0);
				const count = rows.reduce((a, x) => a + (x.asset_count || 0), 0);
				set_kpi("kpi-gross", fmt_money(gross));
				set_kpi("kpi-accum", fmt_money(accum),
					`${gross ? ((accum / gross) * 100).toFixed(1) : "0"}% ${__("of gross")}`);
				set_kpi("kpi-nbv", fmt_money(nbv));

				const hint = document.getElementById("ai-fhint");
				if (hint) {
					hint.style.display = count === 0 ? "block" : "none";
					hint.innerHTML = count === 0
						? __("No assets found for these filters - run ai_seed_data() from the console or check the selected Company.")
						: "";
				}
			})
			.catch(() => {
				set_kpi("kpi-gross", "—", "");
				set_kpi("kpi-accum", "—", "");
				set_kpi("kpi-nbv", "—", "");
			});

		run("ai_asset_value_summary", { group_by: "Location", as_of: today })
			.then((rows) => {
				const top = rows.slice().sort((a, b) => (b.nbv || 0) - (a.nbv || 0)).slice(0, 10);
				draw("ai-f1", "bar", top.map((x) => x.group_value),
					[{ name: __("Net Book Value"), values: top.map((x) => Math.round(x.nbv || 0)) }],
					["#2490ef"], true);
			})
			.catch(() => empty_chart("ai-f1"));

		run("ai_asset_ageing", { as_of: today })
			.then((rows) => {
				const count = rows.reduce((a, x) => a + (x.asset_count || 0), 0);
				const weighted = rows.reduce(
					(a, x) => a + (x.avg_age || 0) * (x.asset_count || 0), 0);
				set_kpi("kpi-age",
					count && weighted ? (weighted / count).toFixed(1) + " " + __("yrs") : "—",
					`${count} ${__("assets")}`);
				draw("ai-f2", "bar", rows.map((x) => x.bucket),
					[{ name: __("Net Book Value"), values: rows.map((x) => Math.round(x.nbv || 0)) }],
					["#813bff"], true);
			})
			.catch(() => empty_chart("ai-f2"));

		run("ai_disposal_register", { from_date: year_ago, to_date: today })
			.then((rows) => {
				const nbv = rows.reduce((a, x) => a + (x.nbv || 0), 0);
				set_kpi("kpi-disposed", String(rows.length), fmt_money(nbv));
				const m = by_month(rows, "disposal_date", "nbv");
				const keys = Object.keys(m).sort();
				draw("ai-f3", "bar", keys.map(month_label),
					[{ name: __("Net Book Value"), values: keys.map((k) => Math.round(m[k])) }],
					["#ec8d30"], true);
			})
			.catch(() => empty_chart("ai-f3"));

		run("ai_end_of_life_alert", { as_of: today, within_months: 12 })
			.then((rows) => {
				set_kpi("kpi-eol", String(rows.length), __("within 12 months"));
				const buckets = {};
				rows.forEach((x) => {
					const mo = x.months_left || 0;
					const b = mo <= 3 ? "0-3" : mo <= 6 ? "4-6" : mo <= 9 ? "7-9" : "10-12";
					buckets[b] = (buckets[b] || 0) + 1;
				});
				const items = Object.entries(buckets).sort();
				draw("ai-f4", "bar", items.map((x) => x[0] + " " + __("months")),
					[{ name: __("Assets"), values: items.map((x) => x[1]) }],
					["#e42137"], false);
			})
			.catch(() => empty_chart("ai-f4"));
	}

	frappe.db
		.get_list("Company", {
			fields: ["name"],
			limit_page_length: 0,
			order_by: "name",
		})
		.then((rows) => {
			const def = frappe.defaults.get_user_default("Company");
			company_select.innerHTML =
				`<option value="">${__("All Companies")}</option>` +
				rows
					.map(
						(r) =>
							`<option value="${frappe.utils.escape_html(r.name)}"${
								r.name === def ? " selected" : ""
							}>${frappe.utils.escape_html(r.name)}</option>`
					)
					.join("");
		});

	company_select.addEventListener("change", () => load());
	drafts_box.addEventListener("change", () => load());

	frappe.call({
		method: "frappe.client.get_value",
		args: { doctype: "Global Defaults", fieldname: "default_currency" },
		callback(r) {
			currency = (r.message && r.message.default_currency) || null;
		},
	});

	load();
};

frappe.pages["asset-finance-hq"].on_page_show = function () {
	/* nothing extra */
};
