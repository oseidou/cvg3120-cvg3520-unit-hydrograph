from pathlib import Path
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from hydro import calibrate, simulate, depth_to_flow

st.set_page_config(page_title='CVG3120 / CVG3520 — Unit Hydrograph', page_icon='💧', layout='wide')
st.title('CVG3120 / CVG3520 — φ-Index & Unit Hydrograph')
st.caption('University of Ottawa · Daily time step · Event-based rainfall–runoff modeling')
intro, help_column = st.columns([2, 1])
with intro:
    st.markdown('**Load daily data → Calibrate one storm → Explore rainfall scenarios**')
    st.caption('Results update automatically when you change a control. Start with the sample data to learn the workflow.')
with help_column:
    manual_path = Path(__file__).resolve().parent / 'docs' / 'CVG3120_CVG3520_User_Manual.pdf'
    if manual_path.is_file():
        st.download_button(
            'Download user manual (PDF)',
            data=manual_path.read_bytes(),
            file_name=manual_path.name,
            mime='application/pdf',
            key='user_manual',
            type='primary',
            on_click='ignore',
            help='Step-by-step instructions, CSV formats, a worked example, and troubleshooting. No external account or website required.',
        )
    else:
        st.info('The PDF manual belongs in the docs folder. Extract the complete app ZIP to restore the download.')
st.warning('**EDUCATIONAL TOOL ONLY** — For teaching and learning. Not validated for flood forecasting, infrastructure design, dam operation, or safety-critical decisions.')

with st.expander('Quick start — try the sample data first'):
    st.markdown('''
1. Leave the upload empty and keep the sample watershed area at **250 km²**.
2. Keep the sample storm dates (**2024-04-05 to 2024-05-03**), straight-line baseflow, and **8-day response length**. You should obtain **φ ≈ 4.50 mm/day**.
3. In section 3, change the rainfall percentage and compare the two simulated hydrographs. Use **0%** for identical rainfall and **−100%** for zero rainfall.

For your watershed, upload your CSV and **replace the area** before interpreting results. Download the manual above for the full instructions.
''')

@st.cache_data
def demo_data():
    dates = pd.date_range('2024-04-01', periods=40, freq='D')
    p = np.zeros(40)
    p[6:15] = [4, 19, 30, 12, 6, 0, 13, 8, 2]
    p[20:24] = [0, 0, 0, 0]
    area = 250.0
    u = depth_to_flow(np.array([0.03, 0.14, 0.27, 0.25, 0.16, 0.09, 0.045, 0.015]), area)
    q = 12 + np.convolve(np.maximum(p - 4.5, 0), u, mode='full')[:40]
    return pd.DataFrame({'date': dates, 'precip_mm': p, 'flow_cms': q})


def csv_bytes(df):
    return df.to_csv(index=False).encode('utf-8')


def load_data(file, columns, title):
    try:
        df = pd.read_csv(file)
    except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError) as exc:
        raise ValueError(f'{title}: use a comma-separated UTF-8 CSV with a header row; see the sample format below.') from exc
    if df.empty:
        raise ValueError(f'{title}: the CSV has no data rows.')
    df.columns = df.columns.str.strip()
    if df.columns.duplicated().any():
        raise ValueError(f'{title}: column names must be unique.')
    if not set(columns).issubset(df.columns):
        missing = ', '.join(c for c in columns if c not in df.columns)
        raise ValueError(f'{title}: missing column(s): {missing}. Required headers: {", ".join(columns)}.')
    df = df[columns].copy()
    date_text = df['date'].astype(str).str.strip()
    if not date_text.str.fullmatch(r'\d{4}-\d{2}-\d{2}').all():
        raise ValueError(f'{title}: use dates in YYYY-MM-DD format, without times (for example, 2024-04-01).')
    df['date'] = pd.to_datetime(date_text, format='%Y-%m-%d', errors='coerce')
    for c in columns:
        if c != 'date':
            df[c] = pd.to_numeric(df[c], errors='coerce')
    if df.isnull().any().any():
        raise ValueError(f'{title}: missing, nonnumeric, or invalid date values detected.')
    numeric_columns = [c for c in columns if c != 'date']
    if not np.isfinite(df[numeric_columns].to_numpy(dtype=float)).all():
        raise ValueError(f'{title}: infinite values are not allowed. Use finite daily measurements.')
    if df['date'].duplicated().any():
        raise ValueError(f'{title}: duplicate dates detected.')
    if any((df[c] < 0).any() for c in columns if c != 'date'):
        raise ValueError(f'{title}: negative values are not allowed.')
    df = df.sort_values('date').reset_index(drop=True)
    if not df.date.diff().dropna().eq(pd.Timedelta(days=1)).all():
        raise ValueError(f'{title}: dates must be continuous at daily intervals (no gaps).')
    return df

with st.expander('ℹ️ How this educational model works', expanded=False):
    st.markdown(r'''
**1. Choose an isolated storm** and include its hydrograph recession. Upload daily observed rainfall and streamflow, and enter watershed area.

**2. Separate baseflow** by either a constant value equal to the first day's flow or a straight line between the start and end flows (capped at observed flow). Direct runoff is observed flow minus baseflow.

**3. Compute the φ-index** (mm/day), a constant daily loss threshold chosen so that
$$\sum_t \max(P_t-\phi,0)=\frac{86,400}{1000A}\sum_t Q_{d,t}$$
where $P$ is daily rainfall in mm, $Q_d$ is direct streamflow in m³/s and $A$ is catchment area in km².

**4. Estimate a daily unit hydrograph** by nonnegative, regularized least-squares deconvolution of effective rainfall and direct flow. UH ordinates have units m³/s per mm of excess rainfall, and are normalized so that 1 mm produces 1 mm of catchment runoff volume.

**5. Simulate new rainfall** by applying the calibrated φ-index and convolving effective rainfall with the estimated unit hydrograph, then adding an assumed **constant baseflow**. Unit-hydrograph routing of effective rainfall is linear and time invariant; the loss threshold means total rainfall and runoff are not generally proportional.

**Important limitations:** The φ-index is **event-specific**, not a physically measured infiltration capacity. Daily data obscure sub-daily rainfall and runoff dynamics; the watershed-average rainfall assumption may fail, and the baseflow method strongly affects the inferred hydrograph. Use isolated events with a clear recession. The calibrated UH and φ-index may not transfer to other seasons, storm types, wetness conditions, or climate regimes. Scenario baseflow is assumed rather than predicted. Review the calibration plot, volume consistency, and Nash–Sutcliffe efficiency (NSE) before interpreting scenarios.
''')

st.subheader('1 · Observed precipitation & streamflow')
st.caption('Use watershed-average daily precipitation and mean daily streamflow for matching dates. At least five daily records are needed for calibration.')
with st.expander('CSV format & units'):
    st.code('date,precip_mm,flow_cms\n2024-04-01,0,12\n2024-04-02,9,12\n2024-04-03,22,14.5', language='csv')
    st.markdown('This is a **format example**, not a complete calibration event. Use dates in **YYYY-MM-DD** format, rainfall in **mm/day**, and mean daily flow in **m³/s**. Use a comma separator and a decimal point. Include every day; enter zero for a known dry day and resolve missing observations before uploading.')
col1, col2 = st.columns([2, 1])
with col1:
    upload = st.file_uploader('Upload a daily CSV', type=['csv'], help='Required columns: date, precip_mm, flow_cms')
    if upload is None:
        obs = demo_data()
        st.info('Using **synthetic demonstration data**. Upload your own CSV to replace them.')
    else:
        try:
            obs = load_data(upload, ['date', 'precip_mm', 'flow_cms'], 'Observed data')
        except Exception as exc:
            st.error(str(exc)); st.stop()
with col2:
    area = st.number_input('Watershed area (km²)', min_value=0.001, value=250.0, step=10.0, format='%.3f', help='The 250 km² default belongs to the sample dataset. Enter the actual contributing area for your watershed.')
    st.download_button('Download sample CSV', csv_bytes(demo_data()), 'sample_daily_rainfall_streamflow.csv', 'text/csv')
    st.caption('250 km² is the sample area. Change it for your own data.')

if len(obs) < 5:
    st.error(f'Observed data contain only {len(obs)} day(s). Upload at least five consecutive daily records, including a storm and its recession.')
    st.stop()
st.caption(f'{len(obs):,} daily records · {obs.date.min():%Y-%m-%d} to {obs.date.max():%Y-%m-%d}')
with st.expander('Preview observed data'):
    st.dataframe(obs, use_container_width=True, hide_index=True)

fig = go.Figure()
fig.add_trace(go.Bar(x=obs.date, y=obs.precip_mm, name='Precipitation (mm/day)', marker_color='#6da7da', yaxis='y2', opacity=0.55))
fig.add_trace(go.Scatter(x=obs.date, y=obs.flow_cms, name='Observed flow (m³/s)', mode='lines', line=dict(color='#0c4967', width=2)))
fig.update_layout(height=320, margin=dict(t=12, l=4, r=4, b=4), xaxis_title='Date', yaxis=dict(title='Flow (m³/s)'), yaxis2=dict(title='Rain (mm/day)', overlaying='y', side='right'), legend=dict(orientation='h', y=1.13))
st.plotly_chart(fig, use_container_width=True)

st.subheader('2 · Calibrate on a storm event')
st.caption('Select one isolated rainfall event. Begin before the flow rises and end after it has returned close to baseflow.')
if upload is not None:
    st.info('The initial dates are a starting selection only. Use the rainfall and flow plot above to select a suitable storm from your data.')
min_date = obs.date.min().date()
max_date = obs.date.max().date()
def_start = obs.date.iloc[max(0, min(4, len(obs) - 5))].date()
def_end = obs.date.iloc[min(len(obs) - 1, 32)].date()
left, right = st.columns(2)
with left:
    start = st.date_input('Event start (include pre-storm baseline)', value=def_start, min_value=min_date, max_value=max_date)
with right:
    end = st.date_input('Event end (include recession)', value=def_end, min_value=min_date, max_value=max_date)
if start > end:
    st.error('Event end must be on or after event start. Adjust the two dates above.')
    st.stop()
event = obs.loc[(obs.date.dt.date >= start) & (obs.date.dt.date <= end)].reset_index(drop=True)
if len(event) < 5:
    st.error('Select at least five consecutive days for calibration.'); st.stop()
st.caption(f'Selected event: {len(event)} days · {event.precip_mm.sum():.1f} mm of precipitation')
opts1, opts2 = st.columns(2)
with opts1:
    base_mode = st.selectbox('Baseflow separation', ['Straight line (first to last day)', 'Constant (first day)'], help='Baseflow is the background flow removed before estimating direct runoff. Both methods are capped at observed flow.')
with opts2:
    duration = st.slider('Unit hydrograph response length (days)', min_value=2, max_value=min(25, len(event)), value=min(8, len(event)), help='Number of daily runoff-response ordinates. The excess-rainfall pulse always lasts one day. Use enough response days to represent the recession.')
with st.expander('Advanced calibration settings'):
    smooth = st.select_slider('Smoothness penalty', options=[0.0, 0.001, 0.01, 0.05, 0.1, 0.5], value=0.01, help='Higher values favor a smoother unit hydrograph, potentially reducing fit. Start with 0.01 and change it only to study sensitivity.')
try:
    fit = calibrate(event.precip_mm, event.flow_cms, area, duration, base_mode, smooth)
except Exception as exc:
    st.error(f'Calibration could not be completed: {exc}'); st.stop()

metrics = st.columns(4)
metrics[0].metric('φ-index', f'{fit.phi_mm_day:.2f} mm/day')
metrics[1].metric('Direct runoff depth', f'{fit.observed_runoff_mm:.2f} mm')
metrics[2].metric('Rainfall excess', f'{fit.excess_total_mm:.2f} mm')
metrics[3].metric('NSE', f'{fit.nse:.2f}' if np.isfinite(fit.nse) else 'N/A')
st.caption('NSE compares modeled and observed direct runoff: 1 is a perfect fit, 0 matches the observed mean benchmark, and negative values are worse. Calibration fit is not independent validation.')
if fit.nse < 0.5:
    st.warning('Event-fit NSE is below 0.5, the app’s teaching flag. Review the event, baseflow, and response length. This flag is not a universal acceptance criterion.')
if not (0.7 <= fit.unit_volume_ratio <= 1.3):
    st.warning(f'Before volume normalization, UH volume was {fit.unit_volume_ratio:.2f} × the theoretical 1-mm volume. This suggests a weakly identified UH; interpret results cautiously.')
if fit.phi_mm_day == 0:
    st.info('Estimated φ = 0; all observed rain contributes to effective rainfall. Check event assumptions and runoff volumes.')

c1, c2 = st.columns([1.4, 1])
st.caption('Assess the fit by comparing Observed direct runoff with UH modeled direct runoff. Observed total flow also includes baseflow.')
with c1:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=event.date, y=event.flow_cms, name='Observed total flow', line=dict(color='#1a5276', width=2)))
    fig.add_trace(go.Scatter(x=event.date, y=fit.baseflow_cms, name='Estimated baseflow', line=dict(color='#7f8c8d', dash='dot')))
    fig.add_trace(go.Scatter(x=event.date, y=fit.direct_cms, name='Observed direct runoff', line=dict(color='#16a085')))
    fig.add_trace(go.Scatter(x=event.date, y=fit.modeled_direct_cms, name='UH modeled direct runoff', line=dict(color='#c0392b', dash='dash')))
    fig.update_layout(title='Event hydrograph / calibration', height=375, margin=dict(l=8,r=8,b=5,t=50), xaxis_title='Date', yaxis_title='Flow (m³/s)')
    st.plotly_chart(fig, use_container_width=True)
with c2:
    fig = go.Figure()
    fig.add_trace(go.Bar(x=np.arange(duration), y=fit.unit_ordinates, marker_color='#2c79a6'))
    fig.update_layout(title='Daily unit hydrograph', height=375, margin=dict(l=8,r=8,b=5,t=50), xaxis_title='Lag (days; first interval = day 0)', yaxis_title='m³/s per mm')
    st.plotly_chart(fig, use_container_width=True)

with st.expander('Calibration tables and downloads'):
    cal_table = event.copy()
    cal_table['baseflow_cms'] = fit.baseflow_cms
    cal_table['observed_direct_cms'] = fit.direct_cms
    cal_table['rain_excess_mm'] = fit.excess_mm
    cal_table['modeled_direct_cms'] = fit.modeled_direct_cms
    st.dataframe(cal_table, use_container_width=True, hide_index=True)
    st.download_button('Download calibration CSV', csv_bytes(cal_table), 'calibration.csv', 'text/csv')
    uh = pd.DataFrame({'lag_day': np.arange(duration), 'unit_hydrograph_cms_per_mm': fit.unit_ordinates})
    st.dataframe(uh, hide_index=True)
    st.download_button('Download unit hydrograph CSV', csv_bytes(uh), 'unit_hydrograph.csv', 'text/csv')

st.subheader('3 · Rainfall–runoff scenarios')
st.caption('Keep the calibrated φ-index and unit hydrograph fixed while changing rainfall. Simulated flows are daily means; their maximum is not an instantaneous flood peak.')
choice = st.radio('Scenario type', ['Increase/decrease event precipitation', 'Upload new daily precipitation'], horizontal=True)
if choice.startswith('Increase'):
    pct = st.slider('Precipitation change (%)', min_value=-100, max_value=200, value=20, step=5)
    st.caption(f'Each day’s precipitation is multiplied by {1 + pct / 100:.2f}. The flow response need not change by the same percentage because the φ-index remains fixed.')
    scenario = event[['date', 'precip_mm']].copy()
    scenario['precip_mm'] = scenario.precip_mm * (1 + pct / 100)
    reference = event[['date', 'precip_mm']].copy()
else:
    st.download_button('Download scenario CSV template', csv_bytes(obs[['date', 'precip_mm']]), 'scenario_rainfall_template.csv', 'text/csv')
    new_upload = st.file_uploader('Upload scenario CSV: date, precip_mm (consecutive daily dates)', type=['csv'], key='scenario')
    if new_upload is None:
        st.info('Upload a scenario rainfall CSV to run this mode. The template above contains only date and precip_mm.')
        st.stop()
    try:
        scenario = load_data(new_upload, ['date', 'precip_mm'], 'Scenario rainfall')
    except Exception as exc:
        st.error(str(exc)); st.stop()
    reference = None

bcol, extra = st.columns([1, 2])
with bcol:
    base_assumed = st.number_input('Assumed scenario baseflow (m³/s)', min_value=0.0, value=float(round(fit.baseflow_cms[0], 3)), step=1.0)
with extra:
    st.caption('Assumes the calibrated φ-index and UH do not change. Scenario baseflow is **constant** and is not predicted from rainfall.')
excess, direct, total = simulate(scenario.precip_mm, fit.phi_mm_day, fit.unit_ordinates, base_assumed)
full_dates = pd.date_range(scenario.date.iloc[0], periods=len(total), freq='D')
result = pd.DataFrame({'date': full_dates, 'precip_mm': np.r_[scenario.precip_mm.to_numpy(), np.zeros(len(total) - len(scenario))], 'effective_rain_mm': np.r_[excess, np.zeros(len(total) - len(scenario))], 'sim_direct_cms': direct, 'sim_total_cms': total})

p1, p2, p3 = st.columns(3)
p1.metric('Scenario rain', f'{scenario.precip_mm.sum():.1f} mm')
p2.metric('Effective rain', f'{excess.sum():.1f} mm')
p3.metric('Maximum simulated daily flow', f'{total.max():.2f} m³/s')
fig = go.Figure()
fig.add_trace(go.Scatter(x=result.date, y=result.sim_total_cms, name='Scenario flow', line=dict(color='#bb4d27', width=3)))
fig.add_trace(go.Scatter(x=result.date, y=result.sim_direct_cms, name='Scenario direct runoff', line=dict(color='#da9e55', dash='dot')))
if reference is not None:
    _, _, ref_flow = simulate(reference.precip_mm, fit.phi_mm_day, fit.unit_ordinates, base_assumed)
    fig.add_trace(go.Scatter(x=full_dates, y=ref_flow, name='Baseline rain scenario flow', line=dict(color='#256c93', dash='dash')))
fig.update_layout(title='Simulated hydrograph (including recession tail)', height=410, xaxis_title='Date', yaxis_title='Flow (m³/s)', margin=dict(l=5,r=5,b=5,t=50))
st.plotly_chart(fig, use_container_width=True)
st.caption(f'The simulation includes {duration - 1} extra dry days to show the response tail. Before the first input day, direct runoff from earlier rainfall is assumed to be zero.')
st.download_button('Download scenario simulation CSV', csv_bytes(result), 'scenario_simulation.csv', 'text/csv')
with st.expander('Scenario time series'):
    st.dataframe(result, use_container_width=True, hide_index=True)
st.caption('CVG3120 / CVG3520 · EDUCATIONAL TOOL ONLY · φ-index and daily unit hydrograph are simplified event-based concepts, not a calibrated operational flood model.')
