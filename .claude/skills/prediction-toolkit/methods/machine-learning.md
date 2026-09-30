# Method 2: Machine Learning

## When to reach for ML

- You have **many features** (>10 dimensions)
- You have **lots of labeled examples** (thousands+)
- The relationship between features and outcome is **nonlinear**
- The task is **pattern-matching on rich signals**, not uncertainty quantification

## When NOT to use ML

- Small data (<100 rows) — use bootstrap or Bayesian
- You need **calibrated uncertainty** — ML gives point predictions; add conformal prediction or Monte Carlo on top
- You need to know **why** (causal) — ML is correlational, not causal
- The pattern is simple (linear, few features) — use statistical forecasting or regression

## What to use (by problem shape)

| Shape | Tool |
|---|---|
| Tabular data, classification/regression | **XGBoost / LightGBM / CatBoost** — dominates Kaggle, fast, explainable via SHAP |
| Tabular, smaller data | **scikit-learn** (RandomForest, GradientBoosting, LogisticRegression) |
| Time-series with many features | **Transformer-based** (TimesFM, Lag-Llama, Chronos) |
| Images | **PyTorch / Hugging Face** (ResNet, ViT, pretrained) |
| Text | **sentence-transformers, LLMs** |
| Anomaly detection | **IsolationForest, LocalOutlierFactor** |

## Quick decision checklist

- [ ] Have you plotted the data and tried a simple linear model first? *(don't skip this)*
- [ ] Do you have enough labeled data? (At least 30 examples per class for classification)
- [ ] Can you define the target variable precisely?
- [ ] Can you evaluate on held-out data?
- [ ] Are you prepared to explain *why* the model predicts what it does? (SHAP, feature importance)

## Integration with this toolkit

ML gives you point predictions. To combine with prediction-toolkit:

1. **Wrap ML predictions in bootstrap CI** — resample training data, retrain, see how much predictions vary.
2. **Use Monte Carlo over model parameters** — sample hyperparameters, evaluate each, build a distribution.
3. **Use Bayesian update when you get new ground truth** — update a rate/probability prior with observed errors.

## Don't do this

- Don't use deep learning when a linear model works
- Don't ignore baseline models (mean, last value, linear regression)
- Don't report a single number without confidence bounds
- Don't call a model "ML" and expect the reader to trust it — show calibration

## External reading

- "The Hundred-Page Machine Learning Book" (Burkov)
- XGBoost paper: Chen & Guestrin 2016
- scikit-learn docs: https://scikit-learn.org/
