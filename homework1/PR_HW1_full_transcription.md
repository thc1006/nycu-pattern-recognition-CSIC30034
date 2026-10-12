<!-- Original PDF: page 1 of 2 -->

# Pattern Recognition / NYCU Fall 2026

**Assignment #1** **(due: 10/16/2026)**

The goal of this assignment is to let you experiment with linear feature spaces. Use **python with numpy** for your experiments. You are allowed to use existing libraries/modules/toolboxes or AI generated codes. However, you need to understand how they work. You are responsible to make your program organized and correct.

Your program/report should include the following:

## 1. Synthetic data specification:

1. **Classes ($C = 3$):** Generate $N = 300$ samples total (100 samples per class).

2. **True Signal Subspace ($d_{\text{signal}} = 3$):**

   - Class 1 mean: $\mu_1 = [+2, +2, 0]^T$
   - Class 2 mean: $\mu_2 = [-2, +2, 0]^T$
   - Class 3 mean: $\mu_3 = [0, -2, 0]^T$
   - Shared within-class covariance in signal dimensions:

     $$
     \Sigma_{\text{signal}} =
     \begin{bmatrix}
     1.0 & 0.6 & 0.0 \\
     0.6 & 1.5 & 0.0 \\
     0.0 & 0.0 & 0.5
     \end{bmatrix}.
     $$

3. **Noise Subspace ($d_{\text{noise}}$ variable):**

   - Append $d_{\text{noise}}$ uninformative noise dimensions generated from $\mathcal{N}(0, \sigma_{\text{noise}}^2)$, where $\sigma_{\text{noise}}^2 = 0.5$.
   - Total feature dimension: $d = d_{\text{signal}} + d_{\text{noise}} = 3 + d_{\text{noise}}$.

Make plots (projected onto 2-D) of the dataset with equal-Mahalanobis-distance contours. See how they look like in different views (projections).

Also make 3-D scatter plots with only the initial 3 signal dimensions together with 95%-confidence ellipsoids for each class.

## 2. Empirical observation of the Hughes phenomenon:

Classifiers to use: (1) 1-NN; (2) Mahalanobis distance based.

Split data into 50/50 training and testing subsets.

Vary the noise dimension (from 1 to 100) and plot the curves of training and testing accuracies.

Vary the splitting (e.g., 20/80 training/testing) to observe whether there are changes.

## 3. Spatial whitening with PCA and ridge regularization:

Plot the eigenvalue spectrum (eigenvalues in descending order).

Repeat Part 2 by applying PCA first to the dataset (with 100 noise dimensions). Vary the projected dimensionality from 1 to 100 (using highest-eigenvalue axes) and plot the curves of training and testing accuracies.

Include ridge regularization in PCA (with varying $\gamma$) and compare their testing accuracy plots.

## 4. Supervised dimensionality reduction:

Apply LDA to the data with 100 noise dimensions. Compare with PCA results.

Compare LDA and regularized LDA results.

## 5. Iris dataset experiment:

Get the Iris dataset. Repeat experiments 2-4 (with your own added 100 noise dimensions). Focus on the Mahalanobis distance based classifier only.

<!-- Original PDF: page 2 of 2 -->

Compare results with and without data normalization of the four features of the Iris dataset.

Observe how the classification accuracy changes with different levels of noise variance.

Write a report (limited to 5 pages, single-spaced) describing the following, according to the requirements mentioned above:

- Methods you have implemented.
- Experiments you have done, and the results. You can include additional experiments not stated above.
- Analysis - Are the results what you expect? Why?

The report (PDF format only) is to be submitted electronically through e3. Also include the program listing (in `*.py` or `*.jpynb` formats) as an appendix to your report (in the same file, not counted toward the page limit).

You can write your report in English or Chinese.

Late submission policy: 10% credit deduction for each day late; up to 3 days late accepted.
