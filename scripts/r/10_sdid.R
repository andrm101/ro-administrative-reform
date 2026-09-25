#!/usr/bin/env Rscript
# Stage 10 — Synthetic DiD (Arkhangelsky et al. 2021) — PLACEBO ANALYSIS
# Romania's reform is hypothetical (2025); no post-2024 data exists.
# Runs a placebo SDiD with pseudo-treatment year 2015 to test whether
# the proposed reform assignment predicts divergence in 2015-2024.
# Expected: ATT ≈ 0 (supports parallel trends for gsynth identification).
#
# Reads:  data/processed/ro_panel_judet.parquet
# Writes: data/processed/ro_sdid_estimates.parquet
#         figures/f10_sdid_weights.png
#         figures/f10_sdid_trend.png

suppressPackageStartupMessages({
  library(arrow)
  library(synthdid)
  library(dplyr)
  library(tidyr)
  library(tibble)
})

cat("=== Stage 10: Synthetic DiD (Placebo, pseudo-treat 2015) ===\n\n")

# --- Path setup ---------------------------------------------------------------
# Detect script location robustly across calling conventions
script_path <- tryCatch(
  normalizePath(sys.frame(1)$ofile, mustWork = FALSE),
  error = function(e) NULL
)
if (is.null(script_path)) {
  # Rscript --file= or sourced context
  args <- commandArgs(trailingOnly = FALSE)
  file_arg <- grep("^--file=", args, value = TRUE)
  if (length(file_arg) > 0) {
    script_path <- normalizePath(sub("^--file=", "", file_arg[1]), mustWork = FALSE)
  }
}

if (!is.null(script_path) && file.exists(script_path)) {
  ROOT <- normalizePath(file.path(dirname(script_path), "..", ".."),
                        mustWork = FALSE)
} else {
  ROOT <- getwd()
}
if (!dir.exists(file.path(ROOT, "data"))) ROOT <- getwd()

DATA_PROC <- file.path(ROOT, "data", "processed")
FIGURES   <- file.path(ROOT, "figures")
dir.create(FIGURES, showWarnings = FALSE, recursive = TRUE)

cat(sprintf("ROOT      : %s\n", ROOT))
cat(sprintf("DATA_PROC : %s\n", DATA_PROC))
cat(sprintf("FIGURES   : %s\n\n", FIGURES))

# --- Constants ----------------------------------------------------------------
PSEUDO_TREAT_YEAR <- 2015L   # placebo treatment year
YEAR_MIN          <- 1995L
YEAR_MAX          <- 2024L

# --- Data ---------------------------------------------------------------------
panel <- read_parquet(file.path(DATA_PROC, "ro_panel_judet.parquet"))
cat(sprintf("Panel loaded: %d rows, %d counties, years %d-%d\n",
            nrow(panel),
            length(unique(panel$nuts3_code)),
            min(panel$year),
            max(panel$year)))
cat(sprintf("Treated counties: %d | Control counties: %d\n\n",
            length(unique(panel$nuts3_code[panel$treated == 1])),
            length(unique(panel$nuts3_code[panel$treated == 0]))))

# --- Outcomes -----------------------------------------------------------------
# Skipped: ln_gva_per_empl (GVA only from 2000 — unbalanced pre-period)
#          unemployment     (NUTS2-broadcast, no county variation)
outcomes <- list(
  list(var = "ln_population",     label = "Log population"),
  list(var = "nat_change_rate",   label = "Natural change rate per 1,000"),
  list(var = "net_migration_rate", label = "Net migration rate per 1,000")
)

# --- Matrix builder -----------------------------------------------------------
make_sdid_matrices <- function(sub, treat_year = PSEUDO_TREAT_YEAR) {
  year_set <- sort(unique(sub$year))
  n_years  <- length(year_set)

  # Retain only balanced units (observed in every year)
  complete_units <- sub |>
    group_by(nuts3_code) |>
    summarise(n = n(), .groups = "drop") |>
    filter(n == n_years) |>
    pull(nuts3_code)
  sub <- sub |> filter(nuts3_code %in% complete_units)

  control_ids <- sub |> filter(treated == 0) |> distinct(nuts3_code) |> pull()
  treated_ids <- sub |> filter(treated == 1) |> distinct(nuts3_code) |> pull()

  if (length(treated_ids) == 0) stop("No treated units remain after balancing.")

  # Wide outcome matrix: control rows first, treated rows last
  Y <- sub |>
    select(nuts3_code, year, value) |>
    pivot_wider(names_from = year, values_from = value) |>
    mutate(.order = if_else(nuts3_code %in% control_ids, 0L, 1L)) |>
    arrange(.order, nuts3_code) |>
    select(-.order) |>
    column_to_rownames("nuts3_code") |>
    as.matrix()

  N0 <- length(control_ids)
  T0 <- sum(year_set < treat_year)

  list(Y = Y, N0 = N0, T0 = T0,
       n_treated = length(treated_ids),
       n_control = length(control_ids))
}

# --- Main loop ----------------------------------------------------------------
results <- list()

for (oc in outcomes) {
  cat(sprintf("[%s]\n", oc$var))

  sub <- panel |>
    filter(
      year >= YEAR_MIN,
      year <= YEAR_MAX,
      !is.na(.data[[oc$var]])
    ) |>
    select(nuts3_code, year, value = all_of(oc$var), treated)

  tryCatch({
    mx <- make_sdid_matrices(sub)
    Y  <- mx$Y
    N0 <- mx$N0
    T0 <- mx$T0

    cat(sprintf("  Units: %d (%d treated, %d control)  T0=%d  T=%d\n",
                nrow(Y), mx$n_treated, mx$n_control, T0, ncol(Y)))

    if (any(is.na(Y))) stop("NAs remain in Y after balancing.")

    est <- synthdid_estimate(Y, N0, T0)

    # Placebo SE requires N0 > N1 (more controls than treated).
    # With 9 controls and 33 treated that condition fails, so we use
    # bootstrap SE (B=200) which has no such restriction.
    # vcov() returns a 1x1 matrix — extract scalar with [1,1].
    se <- tryCatch(
      as.numeric(sqrt(vcov(est, method = "bootstrap",
                           replications = 200L)[1L, 1L])),
      error = function(e) {
        cat(sprintf("  [WARN] bootstrap SE failed (%s) — using NA\n", e$message))
        NA_real_
      }
    )

    att <- as.numeric(est)
    cat(sprintf("  ATT = %.4f  SE = %s\n",
                att,
                if (is.na(se)) "NA" else sprintf("%.4f", se)))

    results[[oc$var]] <- tibble(
      outcome           = oc$var,
      estimator         = "SDiD",
      att               = att,
      se                = se,
      ci_lo             = att - 1.96 * se,
      ci_hi             = att + 1.96 * se,
      n_units           = nrow(Y),
      n_years           = ncol(Y),
      pseudo_treat_year = as.integer(PSEUDO_TREAT_YEAR)
    )

    # Diagnostic plots for ln_population only
    if (oc$var == "ln_population") {
      tryCatch({
        png(file.path(FIGURES, "f10_sdid_weights.png"),
            width = 900, height = 500, res = 120)
        omega     <- attr(est, "weights")$omega
        n_top     <- min(20L, length(omega))
        top_units <- names(sort(omega, decreasing = TRUE))[seq_len(n_top)]
        # synthdid returns ggplot objects — must print() inside png device
        print(synthdid_units_plot(est, units = top_units))
        dev.off()
        cat("  Saved: f10_sdid_weights.png\n")
      }, error = function(e) {
        cat(sprintf("  [WARN] weights plot: %s\n", e$message))
        try(dev.off(), silent = TRUE)
      })

      tryCatch({
        png(file.path(FIGURES, "f10_sdid_trend.png"),
            width = 900, height = 500, res = 120)
        # se.method="bootstrap" can fail internally in synthdid_plot;
        # fall back to se.method="none" so the trend line still renders.
        p <- tryCatch(
          synthdid_plot(est, se.method = "bootstrap"),
          error = function(e2) {
            cat(sprintf("  [INFO] bootstrap se in plot failed, using none: %s\n",
                        e2$message))
            synthdid_plot(est, se.method = "none")
          }
        )
        print(p)
        dev.off()
        cat("  Saved: f10_sdid_trend.png\n")
      }, error = function(e) {
        cat(sprintf("  [WARN] trend plot: %s\n", e$message))
        try(dev.off(), silent = TRUE)
      })
    }

  }, error = function(e) {
    cat(sprintf("  [ERROR] %s\n", conditionMessage(e)))
  })

  cat("\n")
}

# --- Write output -------------------------------------------------------------
if (length(results) > 0) {
  out <- bind_rows(results)
  out_path <- file.path(DATA_PROC, "ro_sdid_estimates.parquet")
  write_parquet(out, out_path)
  cat(sprintf("Written: %s\n", out_path))
  cat(sprintf("  Rows: %d | Columns: %s\n",
              nrow(out), paste(names(out), collapse = ", ")))
  cat("\nEstimates summary:\n")
  print(out[, c("outcome", "estimator", "att", "se", "ci_lo", "ci_hi",
                "pseudo_treat_year")])
} else {
  cat("[WARN] No SDiD estimates produced — parquet not written.\n")
}

cat("\n=== Stage 10 complete ===\n")
