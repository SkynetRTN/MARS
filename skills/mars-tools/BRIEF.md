<!-- Rendered from tools/skill/source/BRIEF.md by `python -m tools.skill`. Edit the source, not this file. -->

MARS: astronomy tools. Before first use read `SKILL.md`; per-domain guides are `references/pulsar.md`, `references/databases.md`, `references/optical.md`, `references/hr.md`, `references/radio.md`.

1. Local tools read only files already here. List or resolve first; never invent a path.
2. Pulsar: load -> compute_pulsar_periodogram -> fold -> sonify. Measure first, compare second. Fold with period_s in either mode. Read false_alarm_assumptions: Gaussian noise bounds are conditional, not pulsar probabilities; fold SNR is empirical. Retune (back_scale at load, start/stop, steps) before a reference fold: not an independent detection. Retuning is outside the single-search bound. 0.016665 s is mains; 2.1-2.2 s is red noise.
3. NED needs a formal designation. ATNF and MPC do zero name resolution (J0534+2200, 1P).
4. Uncap with JSON null, never the text "None".
5. Quote an abstract before attributing a number to a paper; label background knowledge.
6. A preview is a sample; the artifact file is the full result.
