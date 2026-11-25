# CVG3120 / CVG3520 - Phi-Index & Daily Unit Hydrograph

**EDUCATIONAL TOOL ONLY.** For teaching and learning; not for operational flood prediction, infrastructure design, dam operations, or safety-critical decisions.

## Deploy on Streamlit Community Cloud

This repository is ready to deploy as a single Streamlit app.

1. Sign in at https://share.streamlit.io with the GitHub account that owns this repository.
2. Choose **Create app**, then **Yup, I have an app**.
3. Select this repository, branch **main**, and main file path **app.py**.
4. In **Advanced settings**, select **Python 3.12**. No secrets are required.
5. Deploy, then check that the synthetic example shows **4.50 mm/day** and the **Download user manual (PDF)** button works.

Keep the files at the repository root and preserve the `docs/` directory. `requirements.txt` pins the five top-level packages used in the checked runtime. No operating-system packages or PDF-generation packages are needed. GitHub updates to this deployment branch are picked up by Community Cloud.

The repository includes synthetic teaching data only. Browser-uploaded observations are processed by the running app and are not written into this repository.

## Run the app

Extract the entire ZIP and open a terminal in `cvg_unit_hydrograph`. Use Python 3.10 or newer (checked with Python 3.12).

```bash
python -m venv .venv
```

Activate the environment:

- Windows Command Prompt: `.venv\Scripts\activate.bat`
- macOS/Linux: `source .venv/bin/activate`

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

If no browser opens, visit the local URL printed in the terminal. Stop the app with Ctrl+C.

## PDF user manual

Use **Download user manual (PDF)** near the top of the app. The manual is also included at [`docs/CVG3120_CVG3520_User_Manual.pdf`](docs/CVG3120_CVG3520_User_Manual.pdf).

Keep the `docs` folder alongside `app.py`. The download resolves relative to the app file, so launching from another folder also works. The PDF is bundled; no external website or PDF-generation software is needed to use it. It remains accessible when an input file needs correction.

## First run

The app opens with synthetic sample data. Leave the area at **250 km2**, choose **2024-04-05 to 2024-05-03**, and retain straight-line baseflow, **8 response days**, and smoothness **0.01**. Expected results are about **4.50 mm/day** for the phi-index, **61 mm** of direct runoff, and an NSE close to 1. These are teaching data, not observed watershed measurements.

Results update automatically as controls change. Try **0%**, **+20%**, and **-100%** precipitation scenarios. At -100%, simulated direct runoff is zero and total flow equals the assumed constant baseflow.

## Upload format

Observed data require these exact headers:

```csv
date,precip_mm,flow_cms
2024-04-01,0,12
2024-04-02,9,12
2024-04-03,22,14.5
```

This three-row snippet illustrates the format; it is not a complete calibration event. Upload at least five consecutive daily observations and select an isolated storm with its pre-storm baseline and full recession. Use the included 40-day CSV for a complete example.

- `date`: YYYY-MM-DD, no timestamps; one record per day without gaps or duplicate dates.
- `precip_mm`: watershed-average daily precipitation depth, in mm.
- `flow_cms`: mean daily streamflow, in cubic metres per second (m3/s).
- Area: the actual watershed area, in km2. **250 km2 is only the sample default.**

Use a comma-separated UTF-8 file and decimal points. Values must be finite and nonnegative. Fill known dry days with zero; do not treat missing measurements as zero. Rows are sorted by date. A scenario rainfall CSV uses only `date,precip_mm` and may cover new dates.

## What the app does

1. Separate a simple baseflow estimate from observed flow.
2. Calculate the event-specific phi-index so total effective rainfall equals the inferred direct-runoff depth.
3. Fit a nonnegative, smoothed daily unit hydrograph and normalize it to route 1 mm of effective rainfall across the watershed.
4. Apply the fixed phi-index and unit hydrograph to changed or newly uploaded rainfall; add an assumed constant baseflow.

The **rainfall pulse duration is one day**. The response-length slider chooses the number of daily response ordinates; lag 0 is the same daily interval as the rainfall input. The unit hydrograph uses **1 mm**, not the 1 cm convention sometimes used in textbooks.

For calibration, compare **observed direct runoff** with **UH modeled direct runoff**. The observed total-flow curve includes baseflow. Scenario flow includes the entered constant baseflow.

## Limits and interpretation

- Event-based model; it does not track soil moisture, snowmelt, evapotranspiration, changing groundwater storage, or reservoir operations.
- The phi-index is a storm loss threshold, not a measured infiltration capacity. Its value depends on selected dates, area, and baseflow.
- Unit-hydrograph routing assumes linearity and time invariance. The rainfall-loss threshold means total runoff does not necessarily change in the same percentage as total rainfall.
- New rainfall simulations begin with zero direct runoff from rainfall before the first supplied day. Append or prepend relevant observed rainfall when appropriate. The app includes response-length minus one dry days after the last input to display the recession tail.
- Maximum simulated flow is a **daily mean**, not an instantaneous flood peak.
- An NSE below 0.5 triggers a teaching flag, not a universal suitability threshold. A good calibration fit is not independent validation.
- The estimated hydrograph and phi-index may not transfer across storms, seasons, or wetness conditions. Review the manual and plots before interpreting scenarios.

## Files

- `app.py`: Streamlit interface, validation, plots, and downloads.
- `hydro.py`: event-model calculations.
- `requirements.txt`: Python runtime dependencies.
- `sample_daily_rainfall_streamflow.csv`: complete synthetic teaching dataset.
- `docs/CVG3120_CVG3520_User_Manual.pdf`: six-page student manual.

## Interface update

Added a prominent PDF manual download, a sample-data quick start, CSV format and preview panels, explanatory control help, clearer response-length and daily-flow labels, advanced smoothing settings, and friendly input checks. The hydrology engine is unchanged.
