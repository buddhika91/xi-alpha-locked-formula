# Xi-Alpha Locked Formula

A numerical investigation of a locked zero-shell correction to the completed Riemann zeta function \(\Xi\), producing a stable value close to the inverse fine-structure constant.

> **Status:** This repository reports a numerical phenomenon. It is **not** a proof of the Riemann Hypothesis, **not** a proof that the physical fine-structure constant must equal this expression, and **not** a confirmed GUE crack.

## Executive summary

The completed zeta function gives a canonical curvature count

```math
K_2 = -\frac{d^2}{d\gamma^2}\log \Xi\left(\frac12+i\gamma\right)\bigg|_{\gamma=0},
\qquad
A_0 = \frac{2\pi}{K_2}.
```

Numerically,

```math
A_0 \approx 135.97029169825942.
```

A locked Fermi/logistic zero-shell correction gives

```math
A_{\rm corr} \approx 137.03599959487764.
```

Compared with the observed inverse fine-structure constant used in these audits,

```math
\alpha^{-1}_{\rm obs} = 137.035999177000008,
```

the relative error is

```math
\frac{|A_{\rm corr}-\alpha^{-1}_{\rm obs}|}{\alpha^{-1}_{\rm obs}}
\approx 3.0494\times 10^{-9}.
```

The result survived the following numerical hardening checks:

| Audit | Flag |
| --- | --- |
| Formula lock | `XI_ALPHA_GAP_SMOOTH_FORMULA_LOCK_STRONG` |
| Zero/gap convention consistency | `ALPHA_ZERO_SHELL_CONSISTENT_ALPHA_ONLY_NO_GUE_BRIDGE` |
| Component ablation | `XI_ALPHA_LOCKED_FORMULA_COMPONENTS_NECESSARY_STRONG` |
| Symbolic structure / rewrite audit | `XI_ALPHA_LOCKED_FORMULA_SYMBOLIC_STRUCTURE_STRONG` |
| Convergence / universality | `XI_ALPHA_LOCKED_FORMULA_CONVERGENCE_UNIVERSALITY_STRONG` |

## Locked formula

Let \(\gamma_n\) denote the ordinates of the nontrivial zeros on the critical line, indexed by \(n=1,2,3,\ldots\). The locked shell uses

```math
m = 16 = 2^4,
\qquad
c = \frac14,
\qquad
D = 16,
\qquad
\mu = 16+\frac12,
\qquad
\sigma = \frac{1}{\sqrt{2\pi}}.
```

The zero-index Fermi/logistic occupancy is

```math
w_n = \frac{1}{1+\exp\left(\frac{n-\mu}{\sigma}\right)}.
```

The effective zero-shell trace is

```math
Z_{\rm eff}=\frac{\pi}{\sum_n w_n/\gamma_n^2}.
```

The relative shell gap is

```math
r = \frac{Z_{\rm eff}-A_0}{A_0}.
```

The corrected count is

```math
A_{\rm corr}
= A_0\left(1+c\frac{r}{D+|r|}\right)
= A_0\left(1+\frac14\frac{r}{16+|r|}\right).
```

## Main numerical result

Using the locked formula above, the audits found

```math
A_{\rm corr}=137.03599959487764.
```

The observed target used for comparison was

```math
\alpha^{-1}_{\rm obs}=137.035999177000008.
```

The relative error was

```math
3.049400485708\times 10^{-9}.
```

## Why this is interesting

The result is not just a free numerical fit. The strongest audits tested whether the formula is stable under changes that should break a fragile coincidence.

### 1. Zero/gap convention consistency

A previous zero-spacing audit produced a worse locked error because it used a gap-index convention rather than a zero-index convention. The consistency audit showed that once the half-index shift is handled correctly, the formula reproduces the same locked value exactly.

Key result:

```math
A_{\rm corr}^{\rm zero\ index}
= A_{\rm corr}^{\rm shifted\ gap\ index}
= 137.03599959487764.
```

The same audit did **not** confirm a local GUE-spacing bridge.

### 2. Component ablation

The ablation audit replaced one locked component at a time. The locked formula ranked first among tested variants.

Important outputs:

| Quantity | Value |
| --- | --- |
| Locked rank | `1 / 64` |
| Components necessary by more than `10x` damage | `8 / 9` |
| Components necessary by more than `100x` damage | `8 / 9` |
| Fake p-value, locked formula | `0` |
| Fake p-value, best ablated formula | `0` |

The components that were strongly necessary included the zero-shell functional, coefficient, index convention, denominator, center, cutoff shape, center-width pair, and width.

### 3. Symbolic structure audit

The symbolic audit checked whether the locked constants have simple symbolic sources:

| Component | Locked value | Interpretation tested |
| --- | --- | --- |
| Shell index | `16 = 2^4` | dyadic fourth-order shell |
| Midpoint | `16 + 1/2` | midpoint shell |
| Width | `1/sqrt(2*pi)` | Gaussian / heat-kernel normalization |
| Coupling | `1/4` | fourth-order coupling |
| Denominator | `16` | shell degeneracy / normalization |

The same audit found that the formula is stable under trace/Fermi rewrites, while Gaussian, erfc, hard-shell, and raised-cosine replacements were close but not precision-level.

### 4. Convergence and universality

The convergence audit tested zero truncations and numerical precision levels.

The locked value was unchanged across

```math
N_{\rm zeros}=32,64,128,256,512,1024
```

and across

```math
\text{dps}=80,100,120.
```

The reported stability spans were

```math
\text{tail A}_{\rm corr}\text{ relative span}=0,
\qquad
\text{dps A}_{\rm corr}\text{ relative span}=0.
```

Fake and toy zero spectra did not reproduce the real locked value. The finite-sample p-value floor in the convergence audit was

```math
p \approx 0.002079.
```

## Negative results and limitations

This repository deliberately includes negative results.

The following were **not** confirmed:

- A GUE crack.
- A direct local GUE-spacing bridge from the locked alpha shell.
- A Mangoldt/Jacobi response bridge from the alpha shell.
- A Green-kernel transport bridge from the alpha shell to the finite GUE proxy.
- A proof of the Riemann Hypothesis.
- A derivation proving that the physical electromagnetic coupling must be given by this Xi-zero expression.

The honest interpretation is:

> The completed zeta function appears to contain a locked, stable, fake-control-resistant zero-shell formula numerically matching `alpha^-1` to about `3e-9` relative error. The current evidence supports this as a serious numerical phenomenon, but not yet as a theorem or physical derivation.

## Repository contents

Recommended files for this repository:

| File | Purpose |
| --- | --- |
| `rot_rh_xi_alpha_gap_smooth_formula_lock_audit.py` | Finds/checks the locked smooth formula. |
| `rot_rh_alpha_formula_zero_shell_consistency_audit.py` | Resolves the zero-index versus gap-index convention. |
| `rot_rh_xi_alpha_locked_formula_component_ablation_audit.py` | Tests necessity of formula components. |
| `rot_rh_xi_alpha_locked_formula_symbolic_derivation_audit.py` | Tests symbolic structure and trace/Fermi rewrites. |
| `rot_rh_xi_alpha_locked_formula_convergence_universality_audit.py` | Tests truncation, precision, and fake/toy controls. |
| `rot_rh_xi_alpha_locked_formula_report_builder.py` | Builds this report from audit outputs. |

Optional negative GUE bridge scripts may also be included to make clear what was tested and not confirmed.

## Installation

Python 3.10+ is recommended.

```bash
pip install mpmath numpy pandas
```

Some scripts may take several minutes when computing many zeta zeros at high precision. The convergence audit writes a zero cache to speed up reruns.

## Reproducing the report

Run the audit scripts first, then build the report:

```powershell
python rot_rh_xi_alpha_locked_formula_report_builder.py `
  --base-dir "." `
  --out-prefix xi_alpha_locked_formula_report `
  --title "Xi-Alpha Locked Formula Numerical Report" `
  --include-gue-summaries
```

Expected output:

```text
xi_alpha_locked_formula_report.md
xi_alpha_locked_formula_report_manifest.json
AUDIT FLAG: XI_ALPHA_LOCKED_FORMULA_REPORT_BUILT
```

## Recommended citation-style summary

A canonical Xi-curvature count

```math
A_0=\frac{2\pi}{K_2},
\qquad
K_2=-\frac{d^2}{d\gamma^2}\log\Xi\left(\frac12+i\gamma\right)\bigg|_{\gamma=0},
```

is corrected by a locked Fermi/logistic zero-shell trace at

```math
m=16=2^4,
\qquad
\mu=16+\frac12,
\qquad
\sigma=\frac{1}{\sqrt{2\pi}},
\qquad
c=\frac14,
\qquad
D=16,
```

producing

```math
A_{\rm corr}=137.03599959487764,
```

with relative error

```math
3.0494\times 10^{-9}
```

versus the inverse fine-structure constant used as target. The result is ablation-stable, symbolically structured, truncation/dps stable, and fake/toy zero controls do not reproduce it.

## License

Choose a license before publishing. For open scientific code, common choices are MIT, Apache-2.0, or BSD-3-Clause.

## Disclaimer

This repository is exploratory numerical mathematics. It should be read as evidence for a structured numerical phenomenon, not as a claimed proof of RH, a derivation of the fine-structure constant, or a validated physical theory.
