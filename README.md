# PASS-TRACE

## Live Satellite Pass and Reception Monitor

PASS-TRACE is a small, working dashboard for exploring real public ground-station observation records. It collects data from the SatNOGS Network API, then lets you review observation windows, reported status, signal evidence, and demodulated-frame counts by satellite and station.

The dashboard is designed as a practical ground-network data review tool. It does **not** diagnose spacecraft health, treat absent API rows as failed passes, or use ISRO/ISTRAC operational data.

## What it does

- Fetches public SatNOGS observations for a selected UTC date range, following the API's cursor-based `Link` pagination.
- Normalizes each record into a searchable pass table with satellite, NORAD ID, ground station, start/end time, status, waterfall signal status, and demodulated-frame count.
- Summarizes records by API status and station, provides satellite/station filters, and exports filtered results to CSV.
- Caches API responses for ten minutes, limits requests to the selected date range, and reports network/API errors rather than silently substituting synthetic data.

## Run locally

Use Python 3.10 or newer:

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Streamlit will print a local URL, usually `http://localhost:8501`. Choose a UTC date range and wait for the live SatNOGS data to load. The app uses no API key.

## Data source and responsible interpretation

The app uses the public [SatNOGS Network observations API](https://network.satnogs.org/api/observations/) and its documented `start` and `end` filters. The API exposes reported observation status, waterfall status, and demodulated data. SatNOGS states that API data is openly accessible and distributed under the [CC BY-SA license](https://creativecommons.org/licenses/by-sa/4.0/); attribution is included in the interface.

Status and signal labels are presented as reported by SatNOGS. A `good` status is not a spacecraft health diagnosis; `bad` is the network's observation review status. An absent record means only that the selected query returned no record. It is not proof that a satellite pass was missed.

The API returns live community data, so results can change as new observations arrive or records are reviewed. The current UI displays at most 100 records per query to keep the app responsive; narrow the date range if it reports truncation.

## Existing prototype demo

`pass_trace.py` is the original research demo. It runs a separate Isolation Forest baseline check against public OPS-SAT-AD features and a synthetic two-contact alert-grouping simulation. Those two parts are not connected to the live SatNOGS dashboard and do not validate real cross-pass spacecraft telemetry behavior.

To run the original demo:

```bash
python pass_trace.py
```

## References

- [SatNOGS Network API documentation](https://docs.satnogs.org/projects/satnogs-network/en/latest/api.html)
- [SatNOGS Network API reference](https://librespacefoundation.gitlab.io/-/satnogs/satnogs-network/-/jobs/1380080108/artifacts/satnogs-network-api-client/html2/index.html)
- [CelesTrak GP data API](https://celestrak.org/NORAD/documentation/gp-data-formats.php) (not currently required by the dashboard)

