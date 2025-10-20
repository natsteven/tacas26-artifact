library(ggplot2)
library(tidyr)

smt <- read.csv("results/all_times.csv", header=TRUE)

smt$cs_bass <- cumsum(smt$bass_time)
smt$cs_cvc5 <- cumsum(smt$cvc5_time)
smt$cs_ostrich <- cumsum(smt$ostrich_time)
smt$cs_z3 <- cumsum(smt$z3_time)
smt$bench_id <- 1:nrow(smt)

# Reshape to long format for ggplot2
smt_long <- pivot_longer(
  smt,
  cols = c(cs_bass, cs_cvc5, cs_ostrich, cs_z3),
  names_to = "solver",
  values_to = "cumulative_time"
)
# Set custom labels using factor levels (order matters!)
smt_long$solver <- factor(
  smt_long$solver,
  levels = c("cs_bass", "cs_cvc5", "cs_ostrich", "cs_z3"),
  labels = c("BASS", "CVC5", "Ostrich", "Z3-Noodler")
)
# # Set colors for solvers
# solver_colors <- c(
#   cs_bass = "red",
#   cs_ostrich = "green",
#   cs_z3 = "purple"
# )


# Assuming your data is already in long format as 'smt_long'
ggplot(smt_long, aes(x = bench_id, y = cumulative_time, color = solver)) +
  geom_line(size = 0.7) +
  labs(
    x = "Benchmarks Completed",
    y = "Time (s)",
    color = "Solver"
  ) +
    scale_x_continuous(breaks = seq(0, max(smt_long$bench_id), by = 500)) +
    scale_y_continuous(breaks = seq(0, max(smt_long$cumulative_time), by = 20000)) +
  theme_grey(base_size = 16) +
  theme(
    legend.position = "right"
  )

ggsave("plots/smt-plot.png", width = 10, height = 6)
