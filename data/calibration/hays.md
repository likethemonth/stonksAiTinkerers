# Calibration — hays

Point-in-time cutoff: **full frozen corpus**

Each row pairs a guidance figure published *before* a period with the
actual reported *after* it. The bias is shrunk toward zero by
`n / (n + 5)` so a short history cannot swing a forecast far off its
anchor. Sigma is the dispersion about the shrunk mean — the error an
estimator using this correction would actually have made — and is what
the reconciler weights by.
