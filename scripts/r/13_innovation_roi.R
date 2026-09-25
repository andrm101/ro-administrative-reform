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

SUIT_PATH    <- file.path(DATA_PROC, "ro_nuts3_suitability.parquet")
FCST_PATH    <- file.path(DATA_PROC, "ro_pvar_forecasts.parquet")
OUTPUT_PATH  <- file.path(DATA_PROC, "ro_pvar_forecasts_roi.parquet")

REFORM_YEAR  <- 2025
RAMP_YEARS   <- 5   # years over which multiplier ramps from 0 to full effect

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
  select(nuts3_code, tier1_gate, tier1_types)

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

# ── Build innovation_hub path ──────────────────────────────────────────────────
# Only showcase counties appear in the forecast; join limits to those present
counterfactual_rows <- fcst |>
  filter(path == "counterfactual") |>
  left_join(suit, by = "nuts3_code")

# For counties without Tier-1 gate or no annual_uplift: innovation_hub = counterfactual (no uplift)
innovation_rows <- counterfactual_rows |>
  mutate(
    ramp_factor = case_when(
      !tier1_gate | is.na(annual_uplift) ~ 0,
      year < REFORM_YEAR ~ 0,
      year >= REFORM_YEAR & year < REFORM_YEAR + RAMP_YEARS ~
        annual_uplift * (year - REFORM_YEAR + 1) / RAMP_YEARS,
      TRUE ~ annual_uplift
    ),
    # Save original value for band expansion reference
    value_orig = value,
    # Apply uplift only to ln_population (primary demographic outcome)
    # Cumulative ln-uplift: ramp_factor * years_since_reform
    value = if_else(
      variable == "ln_population",
      value + ramp_factor * (year - REFORM_YEAR + 1),
      value
    ),
    # Uncertainty bands expanded 5% of original band width (based on original value)
    lo80 = if_else(variable == "ln_population", lo80 - abs(value_orig - lo80) * 0.05, lo80),
    hi80 = if_else(variable == "ln_population", hi80 + abs(hi80 - value_orig) * 0.05, hi80),
    lo95 = if_else(variable == "ln_population", lo95 - abs(value_orig - lo95) * 0.05, lo95),
    hi95 = if_else(variable == "ln_population", hi95 + abs(hi95 - value_orig) * 0.05, hi95),
    path = "innovation_hub"
  ) |>
  select(-tier1_gate, -tier1_types, -annual_uplift, -dominant_type,
         -ramp_factor, -value_orig)

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
