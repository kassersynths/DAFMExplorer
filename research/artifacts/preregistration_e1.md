# Pre-registration: Experiment E1 (carrier-TL vs modulator-TL)

**Status:** pre-registered before looking at audio-space distances for TL-variant groups.  
**Hypothesis source:** Chowning (1973). The modulation index controls spectral bandwidth in FM synthesis. Operator Total Level is output level, so a carrier-TL change is essentially amplitude while a modulator-TL change changes the modulation index and therefore spectral content.

## Hypothesis

At equal parametric distance, preset pairs that differ only in the TL of a **modulator** show significantly larger perceptual (audio-feature) distance than pairs that differ only in the TL of a **carrier**, measured on the EBU R128-normalised loudness path.

## Primary test

- Mann–Whitney U on pairwise audio distances within TL-variant groups labelled `carrier_only` vs `modulator`.
- Effect size: Cliff's delta with bootstrap CI.
- Inference accounts for nesting inside timbral cores (cluster-robust / within-core permutation).
- Multiple-comparison correction: Benjamini–Hochberg across metrics if more than one is reported.

## Null-result protocol (decided in advance)

1. Repeat on the raw loudness path (loudness normalisation washed out the effect).
2. Repeat with other representation conditions and MFCCD (feature space insensitive).
3. Accept a genuine negative result in this parameter range (modulator TL sits where Bessel response is flat).

## Data

Ground truth is derived from YM2612 algorithm topology and TL-only variant groups in the corpus. No human annotation.
