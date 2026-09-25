# utils.R -- shared helpers for RO-Administrative-Reform R scripts

suppressPackageStartupMessages(library(arrow))

# Project root: resolve relative to this file's location (two levels up from scripts/r/)
# Works when:
#   1. Called as: Rscript scripts/r/some_script.R  (--file= in commandArgs)
#   2. Sourced interactively or via source(...) from project root (falls back to getwd())
proj_root <- function() {
  file_args <- grep("--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
  if (length(file_args) > 0 && nchar(file_args[1]) > 7) {
    script_path <- sub("--file=", "", file_args[1])
    script_path <- normalizePath(script_path, winslash = "/", mustWork = FALSE)
    return(normalizePath(file.path(dirname(script_path), "..", ".."), winslash = "/"))
  }
  # Fallback: assume working directory is the project root
  normalizePath(getwd(), winslash = "/")
}

processed_dir <- function() file.path(proj_root(), "data", "processed")
figures_dir   <- function() file.path(proj_root(), "figures")

read_processed <- function(filename) {
  path <- file.path(processed_dir(), filename)
  if (!file.exists(path)) stop(paste("File not found:", path))
  as.data.frame(read_parquet(path))
}

write_processed <- function(df, filename) {
  dir.create(processed_dir(), showWarnings = FALSE, recursive = TRUE)
  write_parquet(as.data.frame(df), file.path(processed_dir(), filename))
  cat(sprintf("Saved: data/processed/%s (%d rows)\n", filename, nrow(df)))
}
