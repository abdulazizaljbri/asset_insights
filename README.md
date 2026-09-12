# Asset Insights — تقارير الأصول الثابتة

Professional, bilingual (Arabic/English) BI reports and dashboard pages for
**ERPNext v15 Fixed Assets**, built on the same standard as the Warehouse
Insights app.

## What's inside

### Reports (12) — all Script Reports on real ERPNext v15 tables

| Report | Name |
|---|---|
| سجل الأصول التفصيلي | `ai_asset_register` |
| ملخص قيم الأصول | `ai_asset_value_summary` |
| جدول الإهلاك | `ai_depreciation_plan` |
| سجل حركة الأصول والعهدة | `ai_asset_movement_register` |
| جدول الصيانة الدورية | `ai_maintenance_schedule` |
| سجل أعمال الصيانة | `ai_maintenance_log_register` |
| سجل إصلاحات الأصول | `ai_repair_register` |
| سجل تعديل قيم الأصول | `ai_value_adjustment_register` |
| سجل الاستبعاد والبيع | `ai_disposal_register` |
| أصول قرب نهاية العمر الإنتاجي | `ai_end_of_life_alert` |
| أعمار الأصول | `ai_asset_ageing` |
| سجل شراء الأصول | `ai_asset_purchase_register` |

### Dashboard pages (2)

- **Asset Insights HQ** (`/app/asset-insights-hq`) — executive KPIs + charts,
  live from the reports
- **Asset Finance HQ** (`/app/asset-finance-hq`) — depreciation & value focus

### Workspace

Public **Asset Insights** workspace with report cards + shortcuts, shipped as
a standard synced workspace JSON.

## Standing rules honoured by every report

- **Drafts**: nothing draft is ever shown unless the
  **تضمين المسودات / Include Drafts** checkbox is ticked — and when it is,
  drafts appear in every report that can carry them.
- All date filters have sane defaults, so every report always renders.
- Bilingual labels via `translations/ar.csv` (report page titles included).

## Install

```bash
bench get-app <url-of-this-repo>
bench --site <site> install-app asset_insights
bench --site <site> migrate
bench restart
```
