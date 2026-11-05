.libPaths(c("C:/Users/Manuel Q/R/library", .libPaths()))
library(prospect)
args <- commandArgs(trailingOnly = TRUE)
grid <- read.csv(args[1])
out <- NULL
for (i in seq_len(nrow(grid))) {
  g <- grid[i, ]
  r <- prospect(n_struct = g$n, chl = g$cab, car = g$car, ant = g$ant,
                brown = g$brown, ewt = g$ewt, lma = g$lma)
  colnames(r) <- paste0(colnames(r), "_", i)
  out <- if (is.null(out)) r else cbind(out, r)
}
write.csv(out, args[2], row.names = FALSE)
cat("R_LISTO", nrow(grid), "casos\n")
