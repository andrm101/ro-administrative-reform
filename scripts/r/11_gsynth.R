#!/usr/bin/env Rscript
# Stage 11 -- Cross-Country Generalised Synthetic Control (Romania)
# Reads:  data/processed/cc_panel.parquet
# Writes: data/processed/ro_gsynth_raw.parquet
#         figures/f11_gsynth_aggregate.png
#         figures/f11_gsynth_grid.png
#         figures/f11_gsynth_ebar.png

suppressPackageStartupMessages({
  library(arrow)
  library(gsynth)
  library(tidyverse)
})

source("scripts/r/utils.R")
cat("=== Stage 11: Cross-Country GSC (Romania) ===\n\n")

panel <- read_processed("cc_panel.parquet")

# Restrict to units that are complete across all observed years (1995-2024)
observed <- panel |> filter(year <= 2023)
n_years_obs <- n_distinct(observed$year)

complete_units <- observed |>
  group_by(unit_id) |>
  summarise(n_obs = n(), n_na = sum(is.na(ln_population)), .groups = "drop") |>
  filter(n_na == 0, n_obs == n_years_obs) |>
  pull(unit_id)

# Keep complete units; re-attach 2025-2035 rows (NA for RO treated -- gsynth imputes)
panel <- panel |> filter(unit_id %in% complete_units)
ro_treated_ids <- panel |> filter(ro_treated == 1) |> pull(unit_id) |> unique()

n_units_total   <- n_distinct(panel$unit_id)
n_ro_treated    <- length(ro_treated_ids)
n_donors        <- n_units_total - n_ro_treated

cat(sprintf("Balanced panel: %d units (%d RO treated, %d donors)\n",
    n_units_total, n_ro_treated, n_donors))
cat(sprintf("Years: %d--%d | Post-treatment rows (D=1): %d\n",
    min(panel$year), max(panel$year), sum(panel$D, na.rm = TRUE)))

# Abort gracefully if no treated units remain after balancing
if (n_ro_treated == 0) {
  stop("No RO treated units in balanced panel -- check cc_panel.parquet")
}

set.seed(42)
cat("Fitting gsynth (CV over r={0..5}, B=200, estimator=ife)...\n")
cat("Expected runtime: 5-15 minutes.\n")

out <- gsynth(
  ln_population ~ D,
  data      = as.data.frame(panel),
  index     = c("unit_id", "year"),
  force     = "two-way",
  CV        = TRUE,
  r         = c(0, 5),
  se        = TRUE,
  inference = "parametric",
  nboots    = 200,
  seed      = 42,
  min.T0    = 10,
  estimator = "ife"
)

cat(sprintf("Optimal r* = %d\n", out$r.cv))
if (!is.null(out$att) && length(out$att) > 0) {
  cat(sprintf("Average ATT (post-treatment): %.4f\n", mean(out$att, na.rm = TRUE)))
}

# ── Extract counterfactual trajectories from gsynth output ─────────────────
# gsynth (fect wrapper) stores:
#   out$Y.ct  : T x N matrix (all units), no rownames/colnames
#   out$Y.dat : T x N matrix of observed/imputed outcomes
#   out$rawtime : numeric vector of length T with actual year values
#   out$id      : character vector of length N with unit IDs
#   out$tr      : integer indices of treated units within out$id (1-based)
all_years  <- as.integer(out$rawtime)          # length T
all_ids    <- out$id                            # length N
tr_idx     <- out$tr                            # treated column indices

gaps_list <- lapply(seq_along(tr_idx), function(j) {
  col_j      <- tr_idx[j]
  uid        <- all_ids[col_j]
  actual_vec <- as.numeric(out$Y.dat[, col_j])
  ct_vec     <- as.numeric(out$Y.ct[, col_j])
  gap_vec    <- actual_vec - ct_vec   # NA where actual = NA (post-2024 RO treated)
  data.frame(
    unit_id        = uid,
    year           = all_years,
    actual         = actual_vec,
    counterfactual = ct_vec,
    gap            = gap_vec,
    se_gap         = NA_real_,
    stringsAsFactors = FALSE
  )
})

gaps      <- as_tibble(do.call(rbind, gaps_list))
gaps$year <- as.integer(gaps$year)

# Pre-period RMSE per county (fit quality check)
fit_quality <- gaps |>
  filter(year <= 2024) |>
  group_by(unit_id) |>
  summarise(rmse_preperiod = sqrt(mean(gap^2, na.rm = TRUE)), .groups = "drop")

gaps <- gaps |> left_join(fit_quality, by = "unit_id")

write_processed(gaps, "ro_gsynth_raw.parquet")
cat(sprintf("ro_gsynth_raw.parquet: %d rows, %d units\n",
    nrow(gaps), n_distinct(gaps$unit_id)))

# Print fit quality summary
cat("\nPre-period RMSE summary (lower = better synthetic control fit):\n")
print(summary(fit_quality$rmse_preperiod))

# ── Figures ──────────────────────────────────────────────────────────────────
dir.create(figures_dir(), showWarnings = FALSE, recursive = TRUE)

# Figure 1: Aggregate actual vs counterfactual (1995-2024)
tryCatch({
  agg <- gaps |>
    filter(year <= 2024) |>
    group_by(year) |>
    summarise(
      mean_actual = mean(actual, na.rm = TRUE),
      mean_cf     = mean(counterfactual, na.rm = TRUE),
      .groups = "drop"
    )
  p_agg <- ggplot(agg, aes(x = year)) +
    geom_line(aes(y = mean_actual, colour = "Observed"), lwd = 1.2) +
    geom_line(aes(y = mean_cf, colour = "Counterfactual (no reform)"),
              lwd = 1.2, linetype = "dashed") +
    geom_vline(xintercept = 2025, linetype = "dotted", colour = "grey40") +
    scale_colour_manual(values = c("Observed" = "#4d7cff",
                                   "Counterfactual (no reform)" = "#e84d4d")) +
    labs(
      title    = "Mean ln(population): Observed vs. Synthetic Counterfactual",
      subtitle = "33 proposed-demoted Romanian counties | dotted line = proposed reform year (2025)",
      x = "Year", y = "Mean ln(population)", colour = NULL
    ) +
    theme_minimal(base_size = 11) +
    theme(legend.position = "bottom")
  ggsave(file.path(figures_dir(), "f11_gsynth_aggregate.png"),
         p_agg, width = 9, height = 4.5, dpi = 300)
  cat("Saved: f11_gsynth_aggregate.png\n")
}, error = function(e) cat(sprintf("  [WARN] aggregate plot: %s\n", e$message)))

# Figure 2: 3x4 county grid (actual vs counterfactual, 1995-2035)
showcase_units <- ro_treated_ids[seq_len(min(12L, length(ro_treated_ids)))]
tryCatch({
  grid_data <- gaps |>
    filter(unit_id %in% showcase_units) |>
    pivot_longer(cols = c(actual, counterfactual),
                 names_to = "series", values_to = "value") |>
    mutate(series = dplyr::recode(series,
      "actual" = "Observed", "counterfactual" = "Counterfactual"))
  p_grid <- ggplot(grid_data, aes(x = year, y = value, colour = series)) +
    geom_line(lwd = 0.9, na.rm = TRUE) +
    geom_vline(xintercept = 2025, linetype = "dashed", colour = "grey60", lwd = 0.6) +
    facet_wrap(~ unit_id, ncol = 4) +
    scale_colour_manual(values = c("Observed" = "#4d7cff", "Counterfactual" = "#e84d4d")) +
    labs(title = "Observed vs. Synthetic Counterfactual by County",
         x = "Year", y = "ln(population)", colour = NULL) +
    theme_minimal(base_size = 9) +
    theme(legend.position = "bottom", strip.text = element_text(size = 7))
  ggsave(file.path(figures_dir(), "f11_gsynth_grid.png"),
         p_grid, width = 12, height = 9, dpi = 300)
  cat("Saved: f11_gsynth_grid.png\n")
}, error = function(e) cat(sprintf("  [WARN] grid plot: %s\n", e$message)))

# Figure 3: Pre-period RMSE bar (fit quality)
tryCatch({
  fq_sorted <- fit_quality |> arrange(rmse_preperiod)
  p_bar <- ggplot(fq_sorted,
                  aes(x = reorder(unit_id, rmse_preperiod), y = rmse_preperiod)) +
    geom_col(fill = "#4d7cff", alpha = 0.8) +
    coord_flip() +
    labs(title = "Synthetic Control Fit Quality: Pre-period RMSE (1995-2024)",
         subtitle = "Lower RMSE = better match in donor pool",
         x = "County (NUTS3)", y = "RMSE (ln population)") +
    theme_minimal(base_size = 9)
  ggsave(file.path(figures_dir(), "f11_gsynth_ebar.png"),
         p_bar, width = 7, height = 8, dpi = 300)
  cat("Saved: f11_gsynth_ebar.png\n")
}, error = function(e) cat(sprintf("  [WARN] RMSE bar: %s\n", e$message)))

cat("\n=== Stage 11 complete ===\n")
