# PASS-TRACE

## Contact-Aware Telemetry Gap Classification and Alert Triage for Satellite Operations

PASS-TRACE is a student research prototype aligned with satellite mission operations and telemetry analysis.

**Project idea:** distinguish expected no-contact periods from telemetry unexpectedly missing during a scheduled contact, then group related alerts and rank them for operator review.

## Current prototype

The single-file Python demo has two parts:

1. It downloads the public OPS-SAT-AD feature table and evaluates an Isolation Forest baseline using the dataset's `train` split.
2. It simulates telemetry across two communication passes, joins alerts into events, and compares FIFO, alert-score, and PASS-TRACE priority rankings.

The second part is synthetic. It demonstrates the workflow, not real satellite operations. The current code **does not yet classify why data is missing**; expected no-contact versus missing packets during an expected contact is the proposed next feature.

## Run

Install Python 3.10+ and dependencies:

```bash
python -m pip install -r requirements.txt
python pass_trace.py
```

The public dataset check requires an internet connection. If it cannot download the CSV, the script continues with the synthetic simulation. Google Colab can run the same file after uploading it.

## Dataset and limitations

The public OPS-SAT-AD dataset contains expert-labelled telemetry segments and a benchmark train/test split. It supports a **segment-level detector check**, not cross-pass event reconstruction: the curated data is not a continuous contact history. The simulation supplies known contact windows and event labels so the event-linking logic can be explored separately.

The current Isolation Forest result is a baseline, not a new detector or a claim of state-of-the-art performance. Event priority weights, dropout tolerance, and contact schedules are illustrative parameters. They need systematic evaluation across many labelled scenarios before drawing conclusions.

No ISRO or ISTRAC operational telemetry, schedule, or procedure is included or represented.

## Research question

Can a ground-side system reduce avoidable review alerts by distinguishing expected communication gaps from unexpected telemetry loss during an expected contact, while still linking developing events across passes?

Potential evaluation measures include false alerts on expected gaps, detection of injected in-contact data loss, event-linking precision/recall, missed critical events, and review delay under a fixed review capacity.

## References

- [OPS-SAT anomaly benchmark paper](https://www.nature.com/articles/s41597-025-05035-3)
- [ISRO: ISTRAC responsibilities](https://www.isro.gov.in/ISTRAC.html)
- [ISRO: mission support and satellite contact scheduling](https://www.isro.gov.in/MissionSupport.html)

