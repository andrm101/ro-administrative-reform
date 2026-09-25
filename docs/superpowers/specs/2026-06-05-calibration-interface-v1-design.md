# Calibration Pipeline + Interface V1 — Design Spec

**Date:** 2026-06-05
**Status:** Approved for planning
**Predecessor:** `2026-06-05-scenario-engine-design.md` (Plan 1 shipped the engine with `provisional: true` v0 literature priors)
**Scope:** Two coordinated workstreams — (1) replace v0 priors with empirically-estimated coefficients from existing processed data; (2) refine the Policy Lab panel into a decision-maker-ready interface.

---

## 1. Goals

1. **Foundational data engineering.** The scenario engine drives policy decisions; its coefficients must be empirically grounded where the data permits, and honestly cited where it does not. Flip `provisional: false` only after an out-of-sample (OOS) validation gate passes.
2. **Interface V1.** Every number in the Policy Lab must be interpretable by a non-econometrician: readable units (% / p.p.), money framed four ways, and a provenance tooltip (ⓘ) behind every metric.

Non-goals (deferred): full-dashboard layout rework (follow-up plan), external data ingestion (QoG/EQI, ESPON, Rodzina 500+ — a future Plan 3), Moretti-tier calibration.

---

## 2. Architecture

```
scripts/calibration/                       data/dashboard/
  B1_extract_lpirf_betas.py   ─┐
  B2_barro_convergence_gmm.py ─┼──────────► elasticities.json   (provisional:false)
  B3_oos_validation_gate.py   ─┘              (+ per-coefficient provenance metadata)
  B0_run_calibration.py  (orchestrator, seeded, idempotent)

dashboard/src/
  utils/format.ts             (NEW — unit conversion: Δln→%, p.p. formatting, € framings)
  utils/format.test.ts        (NEW)
  components/MetricTooltip.tsx (NEW — ⓘ icon + provenance popover)
  components/CostReadout.tsx   (MODIFY — four money framings)
  components/PolicyLab.tsx     (MODIFY — headline band, % chart, metrics row, convention legend)
```

The calibration scripts read **only** from `data/processed/` (already versioned). They write a single `elasticities.json` with the **same schema** the engine already consumes, plus additive provenance fields. No TypeScript engine changes, no new raw data, no new READMEs. When `provisional` flips to `false`, the engine's existing amber banner disappears automatically.

---

## 3. Calibration — coefficient-by-coefficient

**Identification honesty is the governing principle.** A coefficient is only labelled `empirical` when the estimating variation actually identifies the structural parameter the engine uses it for. Otherwise it stays a literature prior with a proper citation (not a placeholder).

| β | Status | Estimator | Source | `id_strategy` value |
|---|---|---|---|---|
| `beta_gov` | empirical | LP-IRF, annualized mean of ln_gva_per_empl coef over h=1–3 | `ro_lp_irfs.parquet` | `"LP-IRF h1-3 (reform treatment)"` |
| `beta_K_hub` | empirical | Barro β-convergence, hub subset (`proposed_regional_capital==1`), Nickell-corrected FE | `ro_panel_judet.parquet` | `"Barro GMM, hub subset"` |
| `beta_K_sat` | empirical | Barro β-convergence, satellite subset, same spec | `ro_panel_judet.parquet` | `"Barro GMM, satellite subset"` |
| `beta_mig` | empirical (proxy) | LP-IRF net_migration_rate, annualized mean h=1–3 | `ro_lp_irfs.parquet` | `"LP-IRF h1-3 (reform-shock PROXY, not €/cap)"` |
| `lambda` | prior | PL intra-regional migration substitution; co-movement diagnostic reported | literature + `ro_panel_judet.parquet` (diagnostic only) | `"literature prior (conservation not identified — see diagnostics)"` |
| `beta_fert` | prior | Luci-Sobotka (2008), Björklund (2006) fertility-transfer elasticity | literature | `"literature prior (no €/cap fertility shock in panel)"` |
| `beta_edu` | prior | Mincer (1974), OECD returns-to-schooling | literature | `"literature prior (no skills series in panel)"` |
| `gamma` | prior | Holl (2007), ESPON accessibility | literature | `"literature prior (no accessibility data ingested)"` |

**4 empirical (`beta_gov`, `beta_K_hub`, `beta_K_sat`, `beta_mig`-proxy) + 4 priors (`lambda`, `beta_fert`, `beta_edu`, `gamma`).** `tau`, `delta`, `discount_rate`, `moretti` remain assumptions/priors unchanged from v0.

**Why `beta_mig` is flagged a proxy:** the LP-IRF for `net_migration_rate` is identified off the reform-demotion treatment, not off a €/capita retention subsidy. The magnitude is the best available signal but the `id_strategy` string makes the mismatch explicit in the UI tooltip. The engine still multiplies it by the `mu` (€/cap) lever — the proxy assumption is that the structural migration response scales similarly; this is documented as a limitation.

**Why `lambda` cannot be promoted from prior (verified during design):** the reform year is 2025, so `post` is empty in observed data — there is no post-reform period to estimate a hub→satellite conservation ratio from. The historical within-NUTS2 hub/satellite net-migration co-movement is **+0.25** (they move *together* under common regional shocks, not in substitution), so conservation is not identified from observed co-movement either. `lambda` therefore stays a literature prior (PL intra-regional flows). `B2` emits the co-movement correlation into `diagnostics.lambda_comovement` for transparency — we show that we checked.

**Why `beta_fert` stays a prior despite available data:** the panel's `nat_change_rate` LP-IRF shows births *falling* after demotion (a treatment-direction artefact), which has the wrong sign for a pronatalist-transfer elasticity. Using it would be a sign error. Literature prior is the honest choice.

### 3.1 Enhancement — Regime statistical backing
- **Interaction regression:** pool hub+satellite, regress growth on lagged level × hub-dummy interaction. The interaction coefficient tests H0: β_K_hub = β_K_sat. Report the **p-value** into `elasticities.json` as `regime_test: { p_value, stat, df }`.
- **Convergence half-life:** for each β_K, compute `half_life = ln(2) / beta_K` (years) and store in that coefficient's provenance. "The gap closes by half every X years" — the policymaker-facing translation.

### 3.2 Enhancement — Small-sample robustness
- **Block-bootstrap by county** (B=2000, `np.random.seed(42)`) for the four empirical β's. Report bootstrap SE and the 90% percentile CI. With N=42, asymptotic SEs are unreliable; the bootstrap SE replaces the asymptotic `se` field.
- **Empirical support bounds:** set each empirical β's `support` (the engine's extrapolation guardrail) to its bootstrap 90% CI rather than a hand-picked range. Priors keep literature-derived support.

### 3.3 Enhancement — Stationarity compliance (CLAUDE.md mandate)
- Run an **Im-Pesaran-Shin** panel unit-root test on `ln_gva_per_empl` before the Barro regression. β-convergence regressions are Galton's-fallacy / unit-root traps; documenting the test result is required by the project's statistical-rigour standards. Store the result in a top-level `diagnostics` block (`ips_stat`, `ips_pvalue`, `conclusion`). If the series is non-stationary in levels, the Barro spec uses the standard first-difference-on-lagged-level form (already the convergence form) and the diagnostic notes this.

### 3.4 Enhancement — Self-documenting provenance
Each empirical coefficient gains an additive `provenance` object (priors get a lighter version):
```json
"beta_K_sat": {
  "value": 0.22, "se": 0.06, "support": [0.10, 0.34],
  "id_strategy": "Barro GMM, satellite subset", "source": "ro_panel_judet.parquet",
  "provenance": {
    "method": "Barro beta-convergence, Nickell-corrected FE",
    "n_obs": 540, "r2": 0.41, "half_life_years": 14.2,
    "boot_ci_90": [0.10, 0.34], "boot_se": 0.061,
    "estimated_at": "2026-06-05T..Z", "git_sha": "abc1234"
  }
}
```
- **β_gov triangulation cross-check:** compare the LP-IRF `beta_gov` against the existing SDiD ATT (`ro_sdid_estimates.parquet`). Store agreement as `diagnostics.beta_gov_sdid_crosscheck: { lpirf, sdid, ratio, agree: bool }`. Rough agreement is a credibility win for the report; disagreement is flagged, not hidden.

### 3.5 OOS validation gate (`B3`)
- Hold out 1995–2004 as pre-period; estimate on 2005–2023.
- Compare engine-predicted vs LP-IRF actual response at h=1 and h=5; compute RMSE.
- **Gate:** if RMSE ≤ threshold (documented constant, e.g. 1.5× the in-sample residual SD), write `provisional: false`; else keep `true` and emit a warning. The flip is *earned*, not assumed.

---

## 4. Interface V1 — Policy Lab panel

Scope: the Policy Lab sidebar only. The full multi-layer dashboard layout is a follow-up plan.

### 4.1 Panel hierarchy (top → bottom)
1. **Headline band** (always visible): regime badge with p-value (`CONVERGENCE · p=0.03`) + two hero KPIs — Region productivity uplift @2040, Programme cost (NPV).
2. **Overlay chart**: replotted in **% uplift over baseline** (not raw ln). Same gradient/baseline-line technique from Plan 1.
3. **Cost-context block** (four framings of the same money):
   | Metric | Formula |
   |---|---|
   | NPV total (€) | existing `cost2040` |
   | € per capita | `cost2040 / Σ population` |
   | % of regional GVA | `cost2040 / Σ(gva_pc × population)` |
   | **€ per p.p. of uplift** | `cost2040 / (region uplift in p.p.)` |
4. **Outcome metrics row**, each with an **ⓘ MetricTooltip**: Productivity Δ (%), Population Δ (%), HDI proxy Δ (p.p.), Hub opportunity cost (p.p.). Tooltip content is read from the coefficient `provenance` (method, N, CI, half-life).
5. **Levers**: progressive disclosure — groups collapsed by default, expand on click.
6. **Convention legend** (panel footer): one line stating the unit convention.

### 4.2 Unit convention (explicit, consistent)
- **Levels** (productivity, population): **% uplift** = `(e^Δln − 1) × 100`.
- **Rates** (HDI proxy, hub opportunity cost, growth rates): **percentage points (p.p.)**.
- The footer legend states this verbatim so a reader never has to guess.

### 4.3 New units module — `format.ts`
Pure functions, unit-tested:
- `lnDeltaToPct(deltaLn: number): number` → `(e^Δ − 1) × 100`
- `formatPct(x: number, dp?: number): string` → `"+3.2%"`
- `formatPp(x: number, dp?: number): string` → `"+1.4 p.p."`
- `formatEur(x: number): string` → `"€1.2bn"` / `"€4.5m"` (lifted from existing CostReadout `eur()`)
- `costPerCapita`, `costPctGva`, `costPerPpUplift` helpers.

### 4.4 New component — `MetricTooltip.tsx`
Small presentational component: an ⓘ icon that opens a popover. Props: `{ label, provenance }`. Renders method, N, CI, source, half-life (when present), and a one-line plain-English gloss. Pure, no engine logic.

---

## 5. Testing

- **Calibration:** each script asserts output shape, sign sanity (β_K_sat > 0, β_K_sat > β_K_hub expected), seeded determinism (re-run → identical JSON modulo timestamp/sha), and idempotency. OOS gate has a unit test on a synthetic series with a known RMSE.
- **format.ts:** unit tests for each conversion (identity at Δ=0, known % at Δ=0.05, p.p. formatting, € thresholds).
- **MetricTooltip / CostReadout / PolicyLab:** type-check + existing Vitest suite stays green; the engine's 23 tests must not regress.
- **Full verification:** `npm test && npx tsc --noEmit && npm run build` all green; manual smoke test that the amber provisional banner disappears once `provisional:false`, and ⓘ tooltips render calibrated provenance.

---

## 6. Data provenance & reproducibility

- All calibration reads from `data/processed/` (already in git). No new raw sources → no new `data/raw/README.md` required this plan.
- `np.random.seed(42)` in every script with stochastic steps (bootstrap, OOS resampling).
- `B0_run_calibration.py` orchestrates B1–B3 deterministically; re-running produces a byte-identical `elasticities.json` (modulo `estimated_at` / `git_sha`, which are written last and excluded from the determinism assertion).

---

## 7. Limitations (carried into the report)

- `beta_mig` is a reform-shock proxy, not a subsidy-elasticity — flagged in `id_strategy` and the ⓘ tooltip.
- `beta_fert`, `beta_edu`, `gamma` remain literature priors; Plan 3 (external ingestion) replaces them.
- N=42 counties is small; the bootstrap CIs are wide by construction and the UI shows them honestly rather than hiding uncertainty.
- The PL→RO transfer assumption (Lucas critique) inherited from Plan 1 is unchanged and still surfaced.

---

## 8. Future Directions (parked — non-binding)

Across the RO administrative-reform, PL capital-reform, and adjacent EU studies we have generated a broad set of policy-influence ideas (cross-border convergence benchmarking, EU-federal vs national dynamics, strategic-asset and natural-resource layers, manpower/firm-expansion modelling). These are intentionally **out of scope** for this plan and recorded here only so they are not lost. Each would warrant its own brainstorm → spec → plan cycle. This appendix imposes no commitment on V1.
