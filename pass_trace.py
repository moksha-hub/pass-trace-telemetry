"""PASS-TRACE single-file Colab demo.

Run this file in Google Colab or Python. It has two deliberately separate parts:
1) a simple detector check on the public, labelled OPS-SAT-AD feature table;
2) a synthetic contact-pass simulation for event linking and review priority.

The OPS-SAT fragments do not provide a full chronological ground-station contact
record. Therefore, only the second part simulates cross-pass reconstruction, and
that part is not validation on real mission operations data.
"""

import warnings
import urllib.request

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


SEED = 17
DATA_URL = "https://zenodo.org/records/15108715/files/dataset.csv?download=1"


def parse_binary_labels(series):
    """Normalize common 0/1 and nominal/anomaly label encodings to 0/1."""
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().all():
        values = set(numeric.astype(int).unique())
        if values.issubset({0, 1}):
            return numeric.astype(int)
    text = series.astype(str).str.strip().str.lower()
    normal_words = {"0", "normal", "nominal", "false", "no", "regular"}
    anomaly_words = {"1", "anomaly", "anomalous", "true", "yes", "abnormal"}
    mapped = text.map(lambda x: 0 if x in normal_words else (1 if x in anomaly_words else np.nan))
    if mapped.isna().any():
        raise ValueError("Could not interpret all values in the dataset label column.")
    return mapped.astype(int)


def parse_train_split(series):
    """Normalize common train/test split encodings; True means training row."""
    if pd.api.types.is_bool_dtype(series):
        return series.astype(bool)
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().all():
        return numeric.astype(int).astype(bool)
    text = series.astype(str).str.strip().str.lower()
    train_words = {"true", "train", "training", "1", "yes"}
    test_words = {"false", "test", "testing", "0", "no"}
    if not text.isin(train_words | test_words).all():
        raise ValueError("Could not interpret all values in the train split column.")
    return text.isin(train_words)


def run_public_dataset_check():
    """Run a modest, reproducible baseline check if the public CSV is reachable."""
    print("PART A — Public OPS-SAT-AD detector check")
    try:
        frame = pd.read_csv(DATA_URL)
    except Exception as exc:
        print(f"Dataset download was unavailable ({exc}). Continuing with simulation only.")
        return

    lower_to_original = {str(c).strip().lower(): c for c in frame.columns}
    # OPS-SAT-AD's feature table names this target column "anomaly".
    # Also accept "label" for compatible exports or mirrors.
    label_col = lower_to_original.get("anomaly", lower_to_original.get("label"))
    train_col = lower_to_original.get("train")
    if label_col is None or train_col is None:
        print("Downloaded file did not expose expected 'anomaly'/'label' and 'train' columns.")
        print("Columns found:", list(frame.columns))
        print("Continuing with simulation only; inspect the public dataset schema before reporting results.")
        return

    y = parse_binary_labels(frame[label_col])
    is_train = parse_train_split(frame[train_col])
    excluded = {label_col, train_col}
    metadata_words = ("segment", "timestamp", "channel", "sampling", "duration", "index", "id")
    numeric = frame.select_dtypes(include=[np.number]).copy()
    feature_cols = [
        c for c in numeric.columns
        if c not in excluded
        and not any(word in str(c).lower() for word in metadata_words)
        and numeric[c].nunique(dropna=True) > 1
    ]
    if not feature_cols:
        print("No numeric feature columns were identified; continuing with simulation only.")
        return

    from sklearn.ensemble import IsolationForest
    from sklearn.impute import SimpleImputer
    from sklearn.metrics import precision_score, recall_score, f1_score, matthews_corrcoef

    X = numeric[feature_cols].replace([np.inf, -np.inf], np.nan)
    train_mask = is_train.to_numpy()
    test_mask = ~train_mask
    imputer = SimpleImputer(strategy="median")
    X_train = imputer.fit_transform(X.loc[train_mask])
    X_test = imputer.transform(X.loc[test_mask])
    y_train = y.loc[train_mask].to_numpy()
    y_test = y.loc[test_mask].to_numpy()
    nominal_train = X_train[y_train == 0]
    if len(nominal_train) < 10 or len(np.unique(y_test)) < 2:
        print("Insufficient nominal training or two-class test data; continuing with simulation only.")
        return

    model = IsolationForest(contamination="auto", random_state=SEED, n_estimators=200)
    model.fit(nominal_train)
    # IsolationForest returns -1 for outliers and +1 for inliers.
    prediction = (model.predict(X_test) == -1).astype(int)
    print(f"Rows: {len(frame)} | features: {len(feature_cols)} | train: {train_mask.sum()} | test: {test_mask.sum()}")
    print("Held-out metrics (baseline only; not a new benchmark result):")
    print(f"  precision: {precision_score(y_test, prediction, zero_division=0):.3f}")
    print(f"  recall:    {recall_score(y_test, prediction, zero_division=0):.3f}")
    print(f"  F1:        {f1_score(y_test, prediction, zero_division=0):.3f}")
    print(f"  MCC:       {matthews_corrcoef(y_test, prediction):.3f}")
    print("Note: this checks segment-level classification only; it does not validate cross-pass event reconstruction.")


def make_synthetic_stream():
    """Create known-truth telemetry and hide the gap from the ground-side tool."""
    rng = np.random.default_rng(SEED)
    n = 100
    time = np.arange(n)
    temperature = 25 + rng.normal(0, 0.25, n)
    voltage = 5.0 + rng.normal(0, 0.035, n)

    # Simulated event A: a developing two-channel event spanning two passes.
    temperature[32:40] += np.linspace(0.45, 1.5, 8)
    temperature[40:60] += np.linspace(1.6, 2.0, 20)  # hidden during contact gap
    temperature[60:72] += np.linspace(2.0, 1.4, 12)
    voltage[62:72] -= np.linspace(0.12, 0.38, 10)
    # Simulated event B: a separate, stronger single-channel excursion in Pass 2.
    # It creates a competing review item so the three queue orderings can differ.
    voltage[84:91] += 0.8

    data = pd.DataFrame({"time": time, "temperature_C": temperature, "voltage_V": voltage})
    data["contact"] = np.select(
        [data.time < 40, data.time >= 60],
        ["Pass 1", "Pass 2"],
        default="Communication gap",
    )
    data["available_to_ground"] = data["contact"] != "Communication gap"
    return data


def detect_alert_episodes(data, baseline_end=25, threshold=4.0, max_dropout_steps=10):
    """Robust baseline flags, collapsed into per-channel/pass alert episodes."""
    channels = ["temperature_C", "voltage_V"]
    baseline = data.iloc[:baseline_end]
    stats = {}
    for channel in channels:
        median = baseline[channel].median()
        mad = np.median(np.abs(baseline[channel] - median))
        robust_sigma = max(1.4826 * mad, 1e-8)
        stats[channel] = (median, robust_sigma)
        data[channel + "_robust_z"] = (data[channel] - median) / robust_sigma
        # Do not score the same samples used to estimate the nominal baseline.
        data[channel + "_flag"] = (
            (data[channel + "_robust_z"].abs() >= threshold)
            & data["available_to_ground"]
            & (data["time"] >= baseline_end)
        )

    alerts = []
    for channel in channels:
        flagged = data.loc[
            data[channel + "_flag"], ["time", "contact", channel + "_robust_z"]
        ].copy()
        if flagged.empty:
            continue
        # Bridge only short threshold dropouts inside the same pass.
        flagged["run"] = (
            flagged["time"].diff().fillna(max_dropout_steps + 1).gt(max_dropout_steps)
            | flagged["contact"].ne(flagged["contact"].shift())
        ).cumsum()
        for _, run in flagged.groupby("run"):
            peak = run.loc[run[channel + "_robust_z"].abs().idxmax()]
            alerts.append({
                "time": int(run["time"].min()),
                "end_time": int(run["time"].max()),
                "pass": str(peak["contact"]),
                "channel": channel,
                "robust_score": float(abs(peak[channel + "_robust_z"])),
            })
    return data, stats, sorted(alerts, key=lambda item: item["time"])


def reconstruct_events(alerts, lookback=35, priority_weights=(0.50, 0.25, 0.25)):
    """Group alerts across channels/passes and produce explainable review scores."""
    groups = []
    for alert in alerts:
        match = next((group for group in groups
                      if alert["time"] - group["last_time"] <= lookback
                      and (alert["channel"] not in {a["channel"] for a in group["alerts"]}
                           or alert["pass"] not in {a["pass"] for a in group["alerts"]})), None)
        if match is None:
            groups.append({"first_time": alert["time"], "last_time": alert["end_time"], "alerts": [alert]})
        else:
            match["alerts"].append(alert)
            match["last_time"] = max(match["last_time"], alert["end_time"])

    events = []
    for number, group in enumerate(groups, start=1):
        items = group["alerts"]
        channels = sorted({item["channel"] for item in items})
        passes = sorted({item["pass"] for item in items})
        severity = min(max(item["robust_score"] for item in items) / 20.0, 1.0)
        persistence = min(len(items) / 4.0, 1.0)
        cross_channel = (len(channels) - 1) / 1.0  # two simulated channels
        w_severity, w_persistence, w_cross = priority_weights
        score = 100 * (w_severity * severity + w_persistence * persistence + w_cross * cross_channel)
        reasons = []
        if len(channels) > 1:
            reasons.append("alerts on multiple telemetry channels")
        if len(passes) > 1:
            reasons.append("evidence continued across separate contact passes")
        if severity >= 0.5:
            reasons.append("strong deviation from baseline")
        events.append({
            "event_id": f"EV-{number:02d}",
            "first_seen": group["first_time"],
            "last_seen": group["last_time"],
            "channels": ", ".join(channels),
            "passes": ", ".join(passes),
            "alert_count": len(items),
            "max_alert_score": round(max(item["robust_score"] for item in items), 2),
            "priority_score": round(score, 1),
            "review_reason": "; ".join(reasons) if reasons else "single-channel alert; review recommended",
        })
    result = pd.DataFrame(events)
    if not result.empty:
        result["FIFO_rank"] = result["first_seen"].rank(method="first").astype(int)
        result["score_only_rank"] = result["max_alert_score"].rank(ascending=False, method="first").astype(int)
        result["PASS_TRACE_rank"] = result["priority_score"].rank(ascending=False, method="first").astype(int)
        result = result.sort_values("PASS_TRACE_rank")
    return result


def run_simulation():
    print("\nPART B — Synthetic contact-pass simulation")
    data = make_synthetic_stream()
    data, baseline_stats, alerts = detect_alert_episodes(data)
    print("Baseline median and robust sigma:", baseline_stats)
    print("Ground-visible flags:", {c: int(data[c + "_flag"].sum()) for c in ["temperature_C", "voltage_V"]})
    print("Detected alert episodes:")
    print(pd.DataFrame(alerts).to_string(index=False) if alerts else "No alerts detected")
    events = reconstruct_events(alerts)
    print("\nReconstructed review queue:")
    print(events.to_string(index=False) if not events.empty else "No events reconstructed")

    fig, axes = plt.subplots(2, 1, figsize=(11, 6), sharex=True)
    for axis, channel, label in zip(
        axes, ["temperature_C", "voltage_V"], ["Temperature (°C)", "Voltage (V)"]
    ):
        axis.plot(data["time"], data[channel], color="#315a7d", lw=1.5)
        axis.axvspan(40, 59, color="#d8d8d8", alpha=0.7, label="No ground contact")
        axis.axvline(40, color="gray", ls=":")
        axis.axvline(60, color="gray", ls=":")
        axis.set_ylabel(label)
        axis.grid(alpha=0.2)
    axes[0].legend(loc="upper left")
    axes[-1].set_xlabel("Simulated time step")
    plt.tight_layout()
    plt.show()
    print("\nSimulation-only scope: contacts, telemetry chronology, and event labels are synthetic.")
    print("Priority weights and dropout/look-back windows are illustrative; evaluate sensitivity before making claims.")


if __name__ == "__main__":
    run_public_dataset_check()
    run_simulation()

