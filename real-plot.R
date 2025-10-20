library(ggplot2)

real_results <- read.csv("results/real-times-cleaned.csv", fill=TRUE, header=TRUE)

real_ostrich <- data.frame(
  bass = real_results$bass_time,
  ostrich = real_results$ostrich_time
)

# real_ostrich <- read.table("results/ostrich/ostrich-real-", sep="", fill=TRUE, header=TRUE)
# # real_ostrich <- na.omit(real_ostrich)

get_shape <- function(row_number) {
 if (row_number <= 30) {
   return(16)  # Circle
 } else if (row_number <= 53) {
   return(15)  # Square
 } else {
   return(4)   # X
 }
}

library(dplyr)

# Split the data
subset1 <- real_ostrich[1:30, ]
subset2 <- real_ostrich[31:53, ]
subset3 <- real_ostrich[54:77, ]

# Combine subsets
combined_data <- bind_rows(
  mutate(subset1, subset = 1),
  mutate(subset2, subset = 2),
  mutate(subset3, subset = 3)
)

# Create the plot
plot_ostrich <- ggplot(combined_data, aes(x = bass, y = ostrich, shape = factor(subset))) +
  geom_point() +
  geom_abline(intercept = 0, slope = 1,color="red", linetype = "dashed") +
  xlab("MAS Solve Time (s)") +
  ylab("Ostrich Solve Time (s)") +
  scale_x_log10() +
  scale_y_log10() +
  scale_shape_manual(values = c(16, 15, 4), label = c("beasties", "jxml2sql", "mathQuizGame"))  +
  coord_cartesian(ylim=c(1, 1000)) +
  theme(
	axis.title = element_text(size = 16),
	axis.text = element_text(size = 14),
	legend.text = element_text(size = 14)
  ) +
	labs(shape = "Subset") +
  geom_point(size = 5)

ggsave("plots/real-ostrich-plot.png", plot=plot_ostrich, device="png", width=12, height = 8)

real_cvc5 <- data.frame(
  bass = real_results$bass_time,
  cvc5 = real_results$cvc5_time
)

sub1 <- real_cvc5[1:30,]
sub2 <- real_cvc5[31:53,]
sub3 <- real_cvc5[54:77,]

combined_data_cvc5 <- bind_rows(
  mutate(sub1, subset = 1),
  mutate(sub2, subset = 2),
  mutate(sub3, subset = 3)
)

plot_cvc5 <- ggplot(combined_data_cvc5, aes(x = bass, y = cvc5, shape = factor(subset))) +
  geom_point() +
  geom_abline(intercept = 0, slope = 1,color="red", linetype = "dashed") +
  xlab("BASS Solve Time (s)") +
  ylab("CVC5 Solve Time (s)") +
  scale_x_log10() +
  scale_y_log10() +
  scale_shape_manual(values = c(16, 15, 4), label = c("beasties", "jxml2sql", "mathQuizGame"))  +
  theme(
	axis.title = element_text(size = 16),
	axis.text = element_text(size = 14),
	legend.text = element_text(size = 14)
  ) +
	labs(shape = "Subset") +
  geom_point(size = 5)

ggsave("plots/real-cvc5-plot.png", plot=plot_cvc5, device="png", width=12, height = 8)

real_z3 <- data.frame(
  bass = real_results$bass_time,
  z3 = real_results$z3_time
)

sub1 <- real_z3[1:30,]
sub2 <- real_z3[31:53,]
sub3 <- real_z3[54:77,]

combined_data_z3 <- bind_rows(
	mutate(sub1, subset = 1),
	mutate(sub2, subset = 2),
	mutate(sub3, subset = 3)
)

plot_z3 <- ggplot(combined_data_z3, aes(x = bass, y = z3, shape = factor(subset))) +
	geom_point() +
	geom_abline(intercept = 0, slope = 1,color="red", linetype = "dashed") +
	xlab("BASS Solve Time (s)") +
	ylab("Z3-Noodler Solve Time (s)") +
	scale_x_log10() +
	scale_y_log10() +
	scale_shape_manual(values = c(16, 15, 4), label = c("beasties", "jxml2sql", "mathQuizGame"))  +
	theme(
		axis.title = element_text(size = 16),
		axis.text = element_text(size = 14),
		legend.text = element_text(size = 14)
	) +
	labs(shape = "Subset") +
	geom_point(size = 5)

ggsave("plots/real-z3-plot.png", plot=plot_z3, device="png", width=12, height = 8)


library(tidyr)

real_results$cs_bass <- cumsum(real_results$bass_time)
real_results$cs_cvc5 <- cumsum(real_results$cvc5_time)
real_results$cs_ostrich <- cumsum(real_results$ostrich_time)
real_results$cs_z3 <- cumsum(real_results$z3_time)
real_results$bench_id <- 1:nrow(real_results)

# Reshape to long format for ggplot2
smt_long <- pivot_longer(
  real_results,
  cols = c(cs_bass, cs_cvc5, cs_ostrich, cs_z3),
  names_to = "solver",
  values_to = "cumulative_time"
)
# Set custom labels using factor levels (order matters!)
smt_long$solver <- factor(
  smt_long$solver,
  levels = c("cs_z3", "cs_cvc5", "cs_ostrich", "cs_bass"),
  labels = c("Z3-Noodler", "CVC5", "Ostrich", "BASS")
)

ggplot(smt_long, aes(x = bench_id, y = cumulative_time, color = solver)) +
  geom_line(size = 0.7) +
  labs(
    x = "Benchmarks Completed",
    y = "Time (s)",
    color = "Solver"
  ) +
    # scale_x_continuous(breaks = seq(0, max(smt_long$bench_id), by = 500)) +
    # scale_y_continuous(breaks = seq(0, max(smt_long$cumulative_time), by = 20000)) +
  theme_grey(base_size = 16) +
  theme(
    legend.position = "right"
  )

ggsave("plots/real-plot.png", width = 10, height = 6)