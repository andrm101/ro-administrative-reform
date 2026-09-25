# Policy-Lever Scenario Engine — Design Spec

**Date:** 2026-06-05
**Project:** RO-Administrative-Reform (Phase 5, Sub-project A)
**Status:** Approved design — hardened. Ready for user review → implementation plan.

---

## 1. Objective

A prescriptive policy-design tool that lets a policymaker "twitch" reform levers and see the downstream effect on **growth and HDI**, per county and per NUTS2 consolidation region, including the **hub's opportunity cost** of redistributing to satellites. It converts the existing descriptive reform-cost forecasts into an interactive, empirically-calibrated what-if engine.

The headline analytical payload: a region's net response to redistribution reveals whether it sits in an **agglomeration regime** (Krugman/NEG — concentrate at the hub) or a **convergence regime** (Barro–Sala-i-Martin — laggards have higher marginal product of capital). The engine surfaces this regime live.

## 2. Scope

**In scope:** 9 calibrated policy levers; a closed-form, client-side scenario engine overlaying the existing MG-VAR baseline; offline calibration producing `elasticities.json`; a "Policy Lab" dashboard mode; an interim HDI proxy.

**Out of scope (documented limitations, not built):** cross-NUTS2 spatial spillovers; full general-equilibrium feedback (the deferred "live solver" option); real HDI health/education micro-data (Sub-project D); national-asset elasticities (Sub-project B — the engine exposes a *pluggable* lever interface for these).

**Relation to sibling sub-projects:** B (national assets) and D (HDI outcomes) plug into interfaces this spec defines. C (EU benchmarking) is independent. A is built first, interface-first, precisely so B and D know their data contracts.

## 3. Architecture & data flow

Two-stage separation keeps the dashboard static (no runtime backend) while every number traces to a regression.

```
OFFLINE (Python/R, one-time, seeded, versioned)     CLIENT (React/TS, live)
┌──────────────────────────────────────────┐       ┌───────────────────────────┐
│ Calibration scripts                        │ JSON  │ scenario(baseline,        │
│  • estimate β's (GMM / DiD / RD)           │ ────▶ │          coeffs, levers)  │
│  • bootstrap → β point + SE                │       │   → {paths, bands, cost}  │
│  • OOS validation gate (PL pre/post 2010)  │       │ pure function, no I/O     │
│  • write elasticities.json (+ provenance)  │       │ unit-tested in isolation  │
│  • write fiscal_primitives.json            │       │ never mutates baseline    │
└──────────────────────────────────────────┘       └───────────────────────────┘
```

**Artifacts produced offline:**
- `data/dashboard/elasticities.json` — each β with `value`, `se`, `id_strategy`, `source`, `support` (calibration range).
- `data/dashboard/fiscal_primitives.json` — per-county `gva`, `population`, `vitality_index`, `tax_base`, `need_weight`, `absorption`, hub/satellite role, NUTS2 group.

**Client engine** is a pure function `scenario(baseline, coefficients, leverVector) → ScenarioResult`. It reads the existing `forecasts` JSON (status_quo path) and overlays shocks. It **never** edits the baseline files, so the current dashboard is unaffected when the Policy Lab is off.

## 4. Lever taxonomy

Nine active levers across three transmission channels, plus a pluggable slot for Sub-project B. Each lever has: a **unit**, a **bound**, a **temporal profile**, and (except policy dials) a **calibrated β**.

| # | Lever | Symbol | Unit | Bound | Profile | β |
|---|---|---|---|---|---|---|
| 1 | Redistribution share | ρ | fraction of hub tax base | [0, 1] | flow | uses β_K |
| 2 | Cohesion injection | κ | €/capita/yr | [0, 500] | flow | uses β_K |
| 3 | Gov-efficiency gain | g | index gain | [0, 1] | structural | β_gov |
| 4 | Migration-retention subsidy | μ | €/capita/yr | [0, 400] | flow | β_mig |
| 5 | MegaCampus intensity | ι | multiplier | [0, 2] | structural | Moretti (given) |
| 6 | Connectivity | conn | index | [0, 1] | structural | γ (modulator) |
| 7 | Family / pronatalist transfer | f | €/capita/yr | [0, 600] | flow | β_fert |
| 8 | Skills / human-capital | s | % of GVA/yr | [0, 5] | flow | β_edu |
| 9 | Reform-transition offset | offset | fraction | [0, 1] | structural | policy dial |
| — | *(pluggable: strategic-firm, resource — Sub-project B)* | — | — | — | — | data-conditional |

**Temporal profiles:**
- **Structural** (one-off institutional shift): linear ramp over 2025–2030, then hold. Reuses the Stage-13 ramp convention.
- **Flow** (recurring annual spend that builds a stock): perpetual-inventory accumulation
  $\;X_t = (1-\delta)X_{t-1} + \text{flow}_t,\;\delta = 0.05$ (annual depreciation; documented assumption).

## 5. Structural model

### 5.1 Normalization (fixes the dimensional bug)

All productivity-channel shocks are expressed as **fraction of baseline regional GVA committed**, so every β is a dimensionless output elasticity. €-denominated levers are divided by baseline GVA before entering the equations; index levers ([0,1], [0,2]) enter via their own semi-elasticities.

### 5.2 Channel 1 — Productivity / output (acts on `ln_gva_per_empl`)

$$\Delta \ln Y_{c,t} = \varphi^{struct}_t\big[\beta_{gov}\,g_c + \iota\,m_c\,\mathbb{1}^{tier1}_c\big] \;+\; \beta_{edu}\,\tilde{s}_{c,t} \;+\; \beta_K^{eff}\,\frac{\Delta K_{c,t}}{\text{GVA}_c}$$

where $\tilde{s}$ and $\Delta K$ follow the flow (accumulating) profile, and the bracketed structural terms follow the ramp-then-hold profile $\varphi^{struct}_t$.

### 5.3 Fiscal block (defines all primitives)

- **Hub tax base:** $T_{hub} = \tau\cdot\text{GVA}_{hub}$, with $\tau$ = effective regional tax-retention rate (from PL MinFin data; documented).
- **Annual redistributed flow:** $F_t = \rho\,T_{hub}$.
- **Need weight:** $w_s = (1-\text{vitality}_s)\,/\,\sum_{s'}(1-\text{vitality}_{s'})$ — poorer satellites get more.
- **Absorption:** $a_s = \gamma + \text{conn}_s$ — connectivity gates how much capital converts to output.
- **Satellite capital inflow:** $\Delta K^{flow}_{s,t} = F_t\,w_s + \kappa\,P_s$ (cohesion is per-capita).
- **Hub drain:** $\Delta K^{flow}_{hub,t} = -F_t$.
- **Effective capital elasticity:** $\beta_K^{eff,s} = \beta_K^{sat}\,a_s$ (satellites), $\beta_K^{eff,hub} = \beta_K^{hub}$ (hub, no absorption gate).
- Both inflows/drains accumulate via perpetual inventory before entering §5.2.

**Regime sign (the headline):** the region's net output change is positive iff
$$\sum_{s}\beta_K^{sat}\,a_s\,w_s \;>\; \beta_K^{hub}.$$
LHS > RHS ⇒ **convergence regime** (redistribution raises regional output); LHS < RHS ⇒ **agglomeration regime** (it lowers it). Computed live per region.

### 5.4 Channel 2 — Demography (acts on `nat_change_rate`, `net_migration_rate` → `ln_population`)

Explicit population accounting identity (fixes the hand-wave):
$$P_{c,t} = P_{c,t-1}\Big(1 + \tfrac{\text{nat}_{c,t} + \text{mig}_{c,t}}{1000}\Big)$$
$$\text{mig}_{c,t} = \text{mig}^{base}_{c,t} + \beta_{mig}\,\mu_c, \qquad \text{nat}_{c,t} = \text{nat}^{base}_{c,t} + \beta_{fert}\,f_c$$

**Migration conservation (models the intracounty drain):** a share λ of satellite-retained migrants is drawn from the hub:
$$\text{mig}_{hub,t} \mathrel{-}= \lambda \sum_{s}\beta_{mig}\,\mu_s,\qquad \lambda\in[0,1]\text{ calibrated from PL intra-regional flows.}$$
This creates a demographic hub↔satellite trade-off mirroring the fiscal one — retention subsidies in satellites partly cannibalize hub population, which is the real cost the user flagged.

### 5.5 Channel 3 — Reform-cost mitigation

$$\text{reform\_cost}^{eff}_c = \text{att\_avg\_pre}_c\,(1-\text{offset})$$
applied to the gsynth demotion shock. `offset = 0` reproduces the existing gsynth central scenario exactly (consistency anchor).

### 5.6 HDI interim proxy (replaces the placeholder)

$$\text{HDI}^{interim}_{c,t} = \big(I^{inc}_{c,t}\cdot I^{health}_{c,t}\cdot I^{edu}_{c,t}\big)^{1/3}$$
- $I^{inc} = \dfrac{\ln(\text{GVA}_{pc}) - \ln(\min_{EU})}{\ln(\max_{EU}) - \ln(\min_{EU})}$ (EU NUTS3 min/max bounds; standard HDI income form).
- $I^{health} =$ normalized **existing `vitality_index`** — defensible interim wellbeing proxy already in the data.
- $I^{edu} =$ national baseline attainment index $+\ \delta_{edu}\,\tilde{s}_{c,t}$ (skills lever drives the education gain).

Labelled **"HDI proxy (interim)"** in the UI; tooltip states which dimensions are proxied. Sub-project D swaps $I^{health}\!\leftarrow$ life expectancy and $I^{edu}\!\leftarrow$ mean+expected schooling behind the unchanged interface `computeHDI(outcomes) → number`.

### 5.7 Consistency anchors (built-in validation)

| Lever setting | Must reproduce |
|---|---|
| all levers at 0 | `status_quo` baseline path (identity) |
| `ι = 1`, others 0 | existing `innovation_hub` path (Stage 13) within tolerance |
| `offset = 0` | gsynth central reform-cost scenario |

These are asserted as automated tests (§10), preventing double-counting and silent drift.

## 6. Calibration strategy

Each β estimated offline with bootstrap SE, tagged with its identification strategy. Estimators are chosen to address the specific endogeneity threat — naïve OLS is rejected.

| Coefficient | Identification strategy (estimator) | Source | Threat addressed | Strength |
|---|---|---|---|---|
| $\beta_{fert}$ | **Rodzina 500+ (2016) DiD / event-study**, high- vs low-eligibility powiats | GUS powiat fertility | clean quasi-experiment | Strong |
| $\beta_K^{hub},\beta_K^{sat}$ | **System-GMM (Blundell–Bond)** dynamic panel, heterogeneous by initial GDP/capita | PL+EU NUTS3 | Galton/Quah measurement bias in convergence regressions | Strong |
| $\beta_{mig}$ | IV off the 500+ transfer shock (avoids targeting reverse-causality) | PL MinFin transfers + GUS migration | transfers target declining regions | Moderate |
| $\beta_{gov}$ | **PL-1999 reform discontinuity** + country FE; cross-checked vs EQI | Gothenburg QoG / EQI | institutional quality confounding | Moderate |
| $\beta_{edu}$ | Mincerian returns-to-schooling prior + EU `edat` cross-section | Eurostat edat_lfse | — (literature-anchored) | Moderate |
| $\iota\cdot m_c$ | **Reuses Stage-13 Moretti multipliers** (T1=2.5%…T8=0.6%) | existing pipeline | n/a | Given |
| $\gamma$ (connectivity) | Literature prior + **mandatory sensitivity sweep**; flagged in UI | ESPON/JRC accessibility | weak identification | Weak — flagged |
| $\lambda$ (migration conservation) | PL intra-regional gross-flow shares | GUS migration matrix | — | Moderate |
| $\tau,\delta$ | Calibrated constants (PL fiscal data; standard δ=0.05) | PL MinFin / convention | documented assumptions | Assumption |

**Out-of-sample gate:** every estimable β is validated by calibrating on PL pre-2010 and predicting PL 2010–2020; per-outcome RMSE must clear a documented threshold before the RO transfer is accepted. Failures are reported, not hidden.

**Lucas-critique caveat:** elasticities estimated under PL's institutional regime transfer to RO under a structural-similarity assumption — surfaced in the report and a UI tooltip.

## 7. Uncertainty propagation

Each β carries an SE; the engine propagates them into scenario CI bands via the first-order delta method, so every scenario shows a **band, not a false-precise point** (per the project's "CIs over point estimates" standard). The weakly-identified connectivity term contributes a widened band and a visual "low-confidence" flag.

## 8. Budget & cost accounting

- **Total programme cost** readout: $\text{Cost} = \sum_t \frac{1}{(1+r)^{t-2025}}\sum_{\text{flow levers}} \text{flow}_{\ell,t}$, social discount $r = 3\%$.
- **Optional binding budget envelope:** when enabled, lever flows are proportionally scaled to fit a user-set €-envelope, so trade-offs are real rather than free money.
- **Plausibility guardrails:** outputs clamped to economically sane ranges; a scenario that pushes any lever beyond its calibration `support` raises an **extrapolation flag** in the UI.

## 9. Dashboard integration

A new **"Policy Lab"** mode (5th layer toggle, beside the Region view).

- **Lever panel** — sliders grouped by channel (Fiscal / Productivity / Demography / Mitigation); each shows its calibrated β ± SE on hover and a € cost contribution.
- **Two synchronized outputs** — per-county (scenario path overlaid on the baseline forecast chart) and **region-aggregate, reusing the existing `RegionOverlayChart`** to show hub opportunity cost vs satellite gains.
- **Regime badge** — live "AGGLOMERATION — redistribution reduces total output" / "CONVERGENCE — redistribution raises total output" from §5.3.
- **KPI readouts at 2040** — Δgrowth, ΔHDI-proxy, hub opportunity cost (€ + growth pts), total cost — all as bands.
- **Scenario presets** — "Status quo", "Pure agglomeration", "Aggressive convergence", "EU cohesion-funded".
- **Shareable scenarios** — lever vector serialized to **URL query params** (`?rho=0.3&kappa=120&...`) for citable, reproducible scenarios.

## 10. Reproducibility & testing

- Calibration scripts idempotent and seeded (`np.random.seed(42)` / `set.seed(42)`); `elasticities.json` and `fiscal_primitives.json` committed with provenance.
- **Engine unit tests** (pure TS function): identity (all-zero = baseline), offset=1 zeroes reform cost, monotonicity (more subsidy ⇒ more population), MegaCampus ι=1 ≡ innovation_hub, delta-method band widths.
- **Calibration acceptance tests**: coefficient **sign** checks (β_fert>0, β_K^sat>0), **magnitude** within literature bands, **OOS RMSE** under threshold.
- **Consistency tests** mapping engine outputs to existing stage outputs (§5.7).
- **Golden-master**: a fixed lever vector reproduces a checked-in expected `ScenarioResult`.

## 11. Data provenance (new raw sources)

Each new source gets `data/raw/<source>/README.md` (source URL, dataset code, pull date, variable defs) per project convention. APIs are used **once** to pull a static snapshot, then versioned locally — preserving reproducibility and honoring the static-data rule.

| Source | Dataset | Feeds |
|---|---|---|
| Gothenburg QoG | European Quality of Government Index (EQI) | β_gov |
| GUS (PL) | Powiat fertility + migration matrices | β_fert, β_mig, λ |
| Eurostat | `edat_lfse` (attainment), `nama_10r_3gdp` (GVA/capita bounds) | β_edu, I_inc |
| ESPON / JRC | Potential accessibility index | γ (connectivity) |
| PL Ministry of Finance | Subnational fiscal transfers / tax retention | β_mig, τ |

## 12. Limitations (stated up front)

PL→RO elasticity transfer (Lucas critique); partial equilibrium (no national GE feedback); within-region scope (no cross-NUTS2 spillovers); connectivity weakly identified; HDI proxy interim until D; static spatial structure; perpetual-inventory δ and tax-retention τ are documented calibrated assumptions, not estimates.

## 13. Literature anchors

Krugman (1991, NEG); Barro & Sala-i-Martin (1992, convergence); Blundell & Bond (1998, system-GMM); Caselli, Esquivel & Lefort (1996, convergence-regression bias); Moretti (2010, local multipliers); Mincer (1974, returns to schooling); Charron et al. (EQI); Magda et al. / Myck (Rodzina 500+ evaluations); Jordà (2005) and Arkhangelsky et al. (2021) already in the pipeline.

## 14. File map

| Action | Path | Responsibility |
|---|---|---|
| Create | `scripts/calibration/A1_estimate_elasticities.py` | orchestrate β estimation, write JSON |
| Create | `scripts/calibration/A2_fert_did.R` | Rodzina 500+ DiD (β_fert) |
| Create | `scripts/calibration/A3_convergence_gmm.R` | system-GMM (β_K) |
| Create | `scripts/calibration/A4_oos_validation.py` | PL pre/post-2010 RMSE gate |
| Create | `data/raw/{qog_eqi,gus_500plus,espon_access,pl_minfin}/README.md` | provenance |
| Create | `data/dashboard/elasticities.json`, `fiscal_primitives.json` | engine inputs |
| Create | `dashboard/src/engine/scenario.ts` | pure scenario function |
| Create | `dashboard/src/engine/fiscal.ts` | fiscal block + regime sign |
| Create | `dashboard/src/engine/hdi.ts` | interim HDI proxy (swappable for D) |
| Create | `dashboard/src/engine/scenario.test.ts` | engine unit + consistency tests |
| Create | `dashboard/src/components/PolicyLab.tsx` | mode container |
| Create | `dashboard/src/components/LeverPanel.tsx` | grouped sliders |
| Create | `dashboard/src/components/RegimeBadge.tsx` | agglomeration/convergence badge |
| Create | `dashboard/src/components/ScenarioPresets.tsx` | preset buttons |
| Create | `dashboard/src/components/CostReadout.tsx` | budget + KPI readouts |
| Create | `dashboard/src/utils/scenarioUrl.ts` | URL (de)serialization |
| Modify | `dashboard/src/types.ts` | `LeverVector`, `ScenarioResult`, `Elasticities` |
| Modify | `dashboard/src/components/LayerSwitcher.tsx` | add Policy Lab toggle |

## 15. Self-review notes

- **Placeholder scan:** HDI "placeholder" replaced with a concrete interim formula; all fiscal primitives (τ, w, a, λ, δ) defined; no TBD remaining.
- **Internal consistency:** normalization (§5.1) makes every β-times-lever term dimensionless; temporal profiles (§4) consistent between lever table and §5; consistency anchors (§5.7) cross-checked against Stage 13 / gsynth.
- **Scope:** single implementation plan's worth; B/D/C cleanly deferred behind interfaces.
- **Ambiguity:** regime sign, population identity, and migration conservation each given explicit closed form to prevent two-way interpretation.
