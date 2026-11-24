# External EDF-VD Comparator

The project includes an independent dual-criticality benchmark in `rt_dash/imc.py`.

It implements:

- EDF;
- permanently active criticality-first EDF;
- classical EDF with Virtual Deadlines, dropping low-criticality work in HI mode;
- degraded-quality EDF-VD, retaining a declared low-criticality budget in HI mode;
- an RT-DASH-style overrun benchmark using EDF in LO mode and criticality-first dispatch in HI mode.

The benchmark follows the runtime concepts described in:

Di Liu, Jelena Spasic, Gang Chen, Nan Guan, Songran Liu, Todor Stefanov, and Wang Yi, “EDF-VD Scheduling of Mixed-Criticality Systems with Degraded Quality Guarantees,” IEEE Real-Time Systems Symposium, 2016, DOI: 10.1109/RTSS.2016.013.

Important boundary: this comparator uses dual-criticality execution-budget overruns. It is not merged with the smart-home semantic event model. The separation prevents a misleading claim that EDF-VD and RT-DASH use identical mode-switch semantics.
