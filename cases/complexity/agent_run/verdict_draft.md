The claim reproduces in direction: on 1117 monthly observations the timing Sharpe rises from 0.3148 at 60 features to 0.3361 at 1200, with an out-of-sample R-squared of 0.0036 (barely positive).

The formal forecast test is the first real check: the Clark-West statistic is 3.3908, which does beat the no-predictability benchmark by a formal test of accuracy, so at this configuration forecast quality is not obviously absent.

The counterfactual is decisive whichever way that went. Injecting reversal into the returns takes the strategy from 0.3361 to -0.0653, negative in 100% of draws. The model does not learn what the data rewards; it builds the same positions regardless.

Honest limitations: this run used 1200 features rather than the paper's largest configuration, a small number of seeds, and did not test the implementation conventions the paper's own critics raised. It also did not identify what the model is doing instead — only that it is not learning.
