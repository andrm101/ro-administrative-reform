# 13_innovation_roi.R
# Stage 13: Innovation Hub forecast path for demoted Romanian counties.
# Reads ro_nuts3_suitability.parquet (tier1_gate, tier1_types) and
# ro_pvar_forecasts.parquet (status_quo / counterfactual paths).
# Produces ro_pvar_forecasts_roi.parquet with innovation_hub path added.

library(arrow)
library(dplyr)
library(tidyr)
library(readr)
library(stringr)

set.seed(42)

ROOT <- tryCatch({
  # When run via `Rscript scripts/r/13_innovation_roi.R` from project root,
  # getwd() gives the project root directly.
  wd <- getwd()
  # Validate: project root should contain data/processed/
  if (dir.exists(file.path(wd, "data", "processed"))) {
    wd
  } else {
    # Fallback: two levels up from script location
    script_path <- tryCatch(
      normalizePath(sys.frame(1)$ofile),
      error = function(e) NULL
    )
    if (!is.null(script_path)) {
      normalizePath(file.path(dirname(script_path), "..", ".."))
    } else {
      here::here()
    }
  }
}, error = function(e) getwd())
DATA_PROC <- file.path(ROOT, "data", "processed")
SIBLING_ROOT <- normalizePath(file.path(ROOT, ".."))

SUIT_PATH    <- file.path(DATA_PROC, "ro_nuts3_suitability.parquet")
FCST_PATH    <- file.path(DATA_PROC, "ro_pvar_forecasts.parquet")
OUTPUT_PATH  <- file.path(DATA_PROC, "ro_pvar_forecasts_roi.parquet")
ESTIMATE_A_PATH <- file.path(SIBLING_ROOT, "EU-Innovation-Panel", "analysis",
                              "p11_archetype_growth_premium.csv")
ESTIMATE_C_PATH <- file.path(SIBLING_ROOT, "PL-Capital-Reform-DiD", "analysis",
                              "retained_capital_benchmark.csv")

REFORM_YEAR  <- 2025
RAMP_YEARS   <- 5   # years over which multiplier ramps from 0 to full effect

check_sibling_path <- function(path, label) {
  if (!file.exists(path)) {
    stop(sprintf(
      "Missing sibling-project dependency for %s: expected file at %s. %s",
      label, path,
      "Run that project's Stage 13 input script first (see docs/superpowers/specs/2026-09-25-stage13-innovation-roi-design.md)."
    ))
  }
  path
}
check_sibling_path(ESTIMATE_A_PATH, "Estimate A (archetype growth premium)")
check_sibling_path(ESTIMATE_C_PATH, "Estimate C (retained-capital benchmark)")

# Annual GDP/population ln-uplift above counterfactual, per ecosystem type.
# Source: Moretti (2010) local multiplier effects, adapted for Eastern European context.
# T6/T7/T8 anchored to the closest analogous Moretti category rather than given
# independent estimates -- see rationale below each.
MORETTI_MULTIPLIERS <- c(
  T1 = 0.025,  # AI / Machine Learning Hub
  T2 = 0.020,  # Biotechnology / Life Sciences
  T3 = 0.015,  # Semiconductors / Advanced Electronics (advanced manufacturing)
  T4 = 0.012,  # Cleantech / Green Technology
  T5 = 0.010,  # Hyperscale Data Centre Hub
  T6 = 0.014,  # HALEU / Advanced Nuclear Industrial Base
               #   anchored near T3: capital-intensive industrial construction and
               #   long-run supply-chain employment, comparable agglomeration profile
               #   to advanced manufacturing rather than to services/logistics.
  T7 = 0.015,  # Deep-Tech Robotics Campus
               #   anchored at T3: advanced-manufacturing analog (precision assembly,
               #   component supply chains).
  T8 = 0.018   # Quantum / Photonics Research Anchor
               #   anchored near T2: research-institution-led knowledge spillovers
               #   (few production jobs, high knowledge-economy multiplier), not a
               #   production-employment profile.
)

# ── Load inputs ────────────────────────────────────────────────────────────────
suit <- read_parquet(SUIT_PATH) |>
  select(nuts3_code, nuts2_code, tier1_gate, tier1_types)

# Remove pre-existing innovation_hub rows (NaN placeholders from Stage 09)
fcst_raw <- read_parquet(FCST_PATH)
fcst <- fcst_raw |>
  filter(path != "innovation_hub")

stopifnot(nrow(suit) == 42)
cat("Forecast rows (excl. placeholder innovation_hub):", nrow(fcst), "\n")
cat("Variables:", paste(unique(fcst$variable), collapse = ", "), "\n")
cat("Paths present:", paste(unique(fcst$path), collapse = ", "), "\n")

# ── Determine max multiplier per county (highest-scoring Tier-1 type) ──────────
get_max_multiplier <- function(tier1_types_str) {
  if (is.na(tier1_types_str) || tier1_types_str == "") return(NA_real_)
  types <- str_split(tier1_types_str, "\\|")[[1]]
  mults <- MORETTI_MULTIPLIERS[types]
  mults <- mults[!is.na(mults)]
  if (length(mults) == 0) return(NA_real_)
  max(mults)
}

get_dominant_type <- function(tier1_types_str) {
  if (is.na(tier1_types_str) || tier1_types_str == "") return(NA_character_)
  types <- str_split(tier1_types_str, "\\|")[[1]]
  mults <- MORETTI_MULTIPLIERS[types]
  mults <- mults[!is.na(mults)]
  if (length(mults) == 0) return(NA_character_)
  names(mults)[which.max(mults)]
}

suit <- suit |>
  mutate(
    annual_uplift = sapply(tier1_types, get_max_multiplier),
    dominant_type = sapply(tier1_types, get_dominant_type)
  )

cat("Tier-1 counties:", sum(suit$tier1_gate, na.rm = TRUE), "\n")
cat("Uplift range:", paste(range(suit$annual_uplift, na.rm = TRUE), collapse = " - "), "\n")

# ── Load Estimates A and C ──────────────────────────────────────────────────────
# Estimate A: EU-Innovation-Panel's archetype growth premium (archetype_id is an
# integer 0/1, matching that repo's Gold-layer join key -- NOT "A1"/"A2" strings).
# Romanian NUTS2 codes are already the join key used by ro_nuts3_suitability.parquet's
# nuts2_code column; all 8 Romanian NUTS2 regions have a direct 1:1 archetype_id in
# the Gold layer, so no NUTS2-parent lookup/downscaling is needed here (unlike the
# suitability scores in build_nuts3_suitability.py, which are computed at NUTS2 level
# and downscaled -- archetype_id is consumed as-is, at NUTS2 granularity).
estimate_a_raw <- read_csv(ESTIMATE_A_PATH, show_col_types = FALSE) |>
  select(archetype_id, growth_premium_pp) |>
  mutate(estimate_a_annual = growth_premium_pp / 100)  # pp/yr -> ln-uplift/yr

ro_nuts2_archetype <- read_parquet(
  file.path(SIBLING_ROOT, "EU-Innovation-Panel", "data", "gold", "region_profiles_gold.parquet")
) |>
  as.data.frame()
# arrow::read_parquet() already restores the pandas index as a real nuts2_code
# column (unlike Python's pd.read_parquet, which keeps it as an index unless
# reset_index() is called) -- guard rather than assume, since a stale Gold
# parquet without embedded pandas index metadata would need rownames_to_column.
if (!"nuts2_code" %in% colnames(ro_nuts2_archetype)) {
  ro_nuts2_archetype <- tibble::rownames_to_column(ro_nuts2_archetype, "nuts2_code")
}
ro_nuts2_archetype <- ro_nuts2_archetype |>
  filter(str_starts(nuts2_code, "RO")) |>
  select(nuts2_code, archetype_id)

estimate_c_tbl <- read_csv(ESTIMATE_C_PATH, show_col_types = FALSE)
estimate_c_annual <- estimate_c_tbl |>
  filter(city_en == "AVERAGE") |>
  pull(annual_growth_ln)
stopifnot(length(estimate_c_annual) == 1, !is.na(estimate_c_annual))
cat("Estimate C (retained-capital benchmark, AVERAGE):", estimate_c_annual, "\n")

# ── Assemble the three-estimate bracket ─────────────────────────────────────────
suit <- suit |>
  left_join(ro_nuts2_archetype, by = "nuts2_code") |>
  left_join(estimate_a_raw, by = "archetype_id") |>
  mutate(
    estimate_b_annual = annual_uplift,  # existing Moretti-based estimate
    estimate_c_annual = estimate_c_annual,
    bracket_pessimistic = pmin(estimate_a_annual, estimate_b_annual, estimate_c_annual, na.rm = TRUE),
    bracket_optimistic  = pmax(estimate_a_annual, estimate_b_annual, estimate_c_annual, na.rm = TRUE)
  )

cat("Bracket assembled. Pessimistic range:",
    paste(range(suit$bracket_pessimistic, na.rm = TRUE), collapse = " - "), "\n")
cat("Optimistic range:",
    paste(range(suit$bracket_optimistic, na.rm = TRUE), collapse = " - "), "\n")

# ── Build innovation_hub path ──────────────────────────────────────────────────
# Only showcase counties appear in the forecast; join limits to those present
counterfactual_rows <- fcst |>
  filter(path == "counterfactual") |>
  left_join(suit, by = "nuts3_code")

# For counties without Tier-1 gate or no annual_uplift: innovation_hub = counterfactual (no uplift)
compute_ramp <- function(bracket_bound, gated, year) {
  case_when(
    !gated | is.na(bracket_bound) ~ 0,
    year < REFORM_YEAR ~ 0,
    year >= REFORM_YEAR & year < REFORM_YEAR + RAMP_YEARS ~
      bracket_bound * (year - REFORM_YEAR + 1) / RAMP_YEARS,
    TRUE ~ bracket_bound
  )
}

innovation_rows <- counterfactual_rows |>
  mutate(
    ramp_factor = compute_ramp(annual_uplift, tier1_gate, year),
    ramp_factor_pessimistic = compute_ramp(bracket_pessimistic, tier1_gate, year),
    ramp_factor_optimistic  = compute_ramp(bracket_optimistic, tier1_gate, year),
    # Save original value for band expansion reference
    value_orig = value,
    # Apply uplift only to ln_population (primary demographic outcome)
    # Cumulative ln-uplift: ramp_factor * years_since_reform
    value = if_else(
      variable == "ln_population",
      value + ramp_factor * (year - REFORM_YEAR + 1),
      value
    ),
    # Pessimistic/optimistic bracket: same ramp shape as the central (Estimate B)
    # path, using each bound's own ramp so the progression isn't double-applied.
    value_pessimistic = if_else(
      variable == "ln_population",
      value_orig + ramp_factor_pessimistic * (year - REFORM_YEAR + 1),
      NA_real_
    ),
    value_optimistic = if_else(
      variable == "ln_population",
      value_orig + ramp_factor_optimistic * (year - REFORM_YEAR + 1),
      NA_real_
    ),
    # Uncertainty bands expanded 5% of original band width (based on original value)
    lo80 = if_else(variable == "ln_population", lo80 - abs(value_orig - lo80) * 0.05, lo80),
    hi80 = if_else(variable == "ln_population", hi80 + abs(hi80 - value_orig) * 0.05, hi80),
    lo95 = if_else(variable == "ln_population", lo95 - abs(value_orig - lo95) * 0.05, lo95),
    hi95 = if_else(variable == "ln_population", hi95 + abs(hi95 - value_orig) * 0.05, hi95),
    path = "innovation_hub"
  ) |>
  select(-tier1_gate, -tier1_types, -annual_uplift, -dominant_type, -nuts2_code,
         -archetype_id, -growth_premium_pp, -estimate_a_annual, -estimate_b_annual,
         -estimate_c_annual, -bracket_pessimistic, -bracket_optimistic,
         -ramp_factor, -ramp_factor_pessimistic, -ramp_factor_optimistic, -value_orig)

# ── Combine and write ──────────────────────────────────────────────────────────
fcst_out <- bind_rows(fcst, innovation_rows) |>
  arrange(nuts3_code, variable, path, year)

write_parquet(fcst_out, OUTPUT_PATH)
cat("Written:", OUTPUT_PATH, "\n")
cat("Rows:", nrow(fcst_out), "(was", nrow(fcst), "+ added", nrow(innovation_rows), "innovation_hub rows)\n")
cat("Paths now:", paste(sort(unique(fcst_out$path)), collapse = ", "), "\n")

# ── Summary table ──────────────────────────────────────────────────────────────
cat("\nCounty-level multiplier assignments:\n")
suit |>
  select(nuts3_code, tier1_gate, tier1_types, annual_uplift, dominant_type) |>
  arrange(desc(annual_uplift)) |>
  print(n = 42)
