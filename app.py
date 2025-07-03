import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import time
from database_handler import DatabaseHandler, DB_PATH
from data_loader import DataLoader
import os
import shutil
from datetime import datetime, date
import pandas as pd
import logging
import sqlite3

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_plotly_layout(theme: str = "Light") -> dict:
    is_dark = theme == "Dark"
    font_color = 'white' if is_dark else '#111111'
    return dict(
        template='plotly_dark' if is_dark else 'plotly',
        plot_bgcolor='#0e1117' if is_dark else 'white',
        paper_bgcolor='#0e1117' if is_dark else 'white',
        font=dict(color=font_color),
        xaxis=dict(tickfont=dict(color=font_color), title=dict(font=dict(color=font_color))),
        yaxis=dict(tickfont=dict(color=font_color), title=dict(font=dict(color=font_color))),
        legend=dict(font=dict(color=font_color)),
        legend_title=dict(font=dict(color=font_color)),
        hovermode='x unified'
    )

def render_individual_graphs(df_filtered, selected_channels, theme: str = "Light"):
    st.subheader("\U0001F4C9 Individual Channel Graphs")
    color_palette = px.colors.qualitative.Set1
    is_dark = theme == "Dark"

    for idx, ch in enumerate(selected_channels):
        st.markdown(f"### {ch}")
        df_ch = df_filtered[["datetime", ch]].dropna()

        if df_ch.empty:
            st.warning(f"\u26A0\uFE0F No data for {ch}")
            continue

        df_ch[ch] = pd.to_numeric(df_ch[ch], errors="coerce")
        df_ch.dropna(subset=[ch], inplace=True)

        if df_ch.empty:
            st.warning(f"\u26A0\uFE0F No valid numeric data for {ch}")
            continue

        y_min, y_max = df_ch[ch].min(), df_ch[ch].max()

        if y_min < 0 and y_max > 0:
            max_variation = max(abs(y_min), abs(y_max))
            padded = max_variation * 1.2
            y_range = [-padded, padded]
        else:
            y_pad = (y_max - y_min) * 0.2 if y_max != y_min else 0.05
            y_range = [y_min - y_pad, y_max + y_pad]

        color = color_palette[idx % len(color_palette)]

        fig_ch = px.line(
            df_ch,
            x='datetime',
            y=ch,
            title=ch,
            labels={'datetime': 'Date & Time', ch: 'Measurement [mm]'},
            template='plotly_dark' if is_dark else 'plotly'
        )
        fig_ch.update_traces(line=dict(color=color))
        fig_ch.update_layout(
            yaxis_range=y_range,
            **get_plotly_layout(theme)
        )

        st.plotly_chart(fig_ch, use_container_width=True)


def render_combined_normalised_graph(df: pd.DataFrame, all_channel_cols: list[str], theme: str, start_date_default: date, end_date_default: date):
    if df.empty:
        st.warning("\U0001F4EC No records for selected range")
        return

    df_melted = df.melt(id_vars='datetime', value_vars=all_channel_cols,
                        var_name='Sensor', value_name='Value')
    # print(f"\nMelted DataFrame:\n{df_melted.head()}")
    if df_melted.empty:
        st.warning("\u26A0\uFE0F Melted data is empty. Nothing to plot.")
        return

    st.subheader("\U0001F4C8 Combined Normalised Graph")
    fig = px.line(df_melted, x='datetime', y='Value', color='Sensor',
                  title=f"Sensor Data from {start_date_default} to {end_date_default}",
                  labels={'datetime': 'Date & Time', 'Value': 'Measurement [mm]'},
                  template='plotly_dark' if theme == "Dark" else 'plotly')
    fig.update_layout(**get_plotly_layout(theme))
    st.plotly_chart(fig, use_container_width=True)


def render_statistics(df: pd.DataFrame, columns: list[str]):
    with st.form("stats_form"):
        selected_col = st.selectbox("\U0001F4CA Select a channel for stats/histogram:", options=columns)
        submitted = st.form_submit_button("Generate Stats")

    if submitted and selected_col:
        values = pd.to_numeric(df[selected_col], errors="coerce").dropna()
        if values.empty:
            st.warning("\u26A0\uFE0F No valid numeric data to show statistics.")
            return

        mean_val = values.mean()
        std_val = values.std()
        min_val = values.min()
        max_val = values.max()
        data_range = max_val - min_val
        bin_width = max(data_range / 100, 0.001)
        nbins = int(data_range / bin_width)

        st.markdown(f"**Mean:** {mean_val:.5f}")
        st.markdown(f"**Standard Deviation:** {std_val:.5f}")

        fig_hist = go.Figure(data=[go.Histogram(x=values, nbinsx=nbins)])
        fig_hist.update_layout(
            title=f"Distribution of {selected_col}",
            xaxis_title=selected_col,
            yaxis_title="Count",
            **get_plotly_layout(st.session_state.get("theme", "Light"))
        )
        st.plotly_chart(fig_hist, use_container_width=True)


def backup_database(db_path: str = DB_PATH, backup_dir: str = "backups") -> str:
    # Check if the DB file even exists
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database file not found: {db_path}")

    # Check if the DB contains data
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get list of all user tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]

        if not tables:
            print("⚠️ No tables found in the database. Skipping backup.")
            return ""

        # Check if any table has rows
        has_data = False
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            if count > 0:
                has_data = True
                break

        conn.close()

        if not has_data:
            print("⚠️ Database is empty. Skipping backup.")
            return ""

    except sqlite3.Error as e:
        raise RuntimeError(f"Error checking database content: {e}")

    # Create backup
    script_dir = os.path.dirname(os.path.abspath(__file__))
    backup_dir_full = os.path.join(script_dir, backup_dir)
    os.makedirs(backup_dir_full, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(backup_dir_full, f"sensor_data_backup_{timestamp}.db")
    shutil.copy2(db_path, backup_file)
    print(f"✅ Database backed up to: {backup_file}")
    return backup_file


# ---------------- APP START ------------------------------------------------------------------------------------------------

st.title("\U0001F4CA Multi-Sensor Data Explorer")
st.session_state["theme"] = st.sidebar.radio("Theme", ["Light", "Dark"], index=0)

db = DatabaseHandler()
df_all = db.load_all_data()

if not df_all.empty:
    df_all = df_all.sort_values("datetime")
    all_channel_cols = [col for col in df_all.columns if col.endswith("diff")]

    # Initialize session state defaults
    if "start_date" not in st.session_state:
        st.session_state["start_date"] = df_all["datetime"].min().date()
    if "end_date" not in st.session_state:
        st.session_state["end_date"] = df_all["datetime"].max().date()
    if "selected_channels" not in st.session_state:
        st.session_state["selected_channels"] = all_channel_cols.copy()

    with st.form("filter_form"):
        start_date = st.date_input("Start Date", st.session_state["start_date"])
        end_date = st.date_input("End Date", st.session_state["end_date"])
        selected_channels = st.multiselect(
            "Select Channels",
            options=all_channel_cols,
            default=st.session_state["selected_channels"],
        )
        if st.form_submit_button("Apply Filters"):
            st.session_state["start_date"] = start_date
            st.session_state["end_date"] = end_date
            st.session_state["selected_channels"] = selected_channels

    # Now work with the persisted state
    if not st.session_state["selected_channels"]:
        st.warning("\u26A0\uFE0F No channels selected. Defaulting to all available.")
        st.session_state["selected_channels"] = all_channel_cols.copy()

    df_filtered = df_all[
        (df_all['datetime'].dt.date >= st.session_state["start_date"]) &
        (df_all['datetime'].dt.date <= st.session_state["end_date"])
    ]

    if df_filtered.empty:
        st.warning("\U0001F4EC No records for selected range")
    else:
        render_combined_normalised_graph(
            df_filtered,
            st.session_state["selected_channels"],
            st.session_state["theme"],
            st.session_state["start_date"],
            st.session_state["end_date"]
        )
        render_individual_graphs(
            df_filtered,
            st.session_state["selected_channels"],
            theme=st.session_state["theme"]
        )
        render_statistics(df_filtered, st.session_state["selected_channels"])

st.markdown("---")
st.subheader("\U0001F4C4 Upload New Sensor File")

uploaded_file = st.file_uploader("Upload Excel or CSV File", type=["csv", "xlsx", "xls"])
if uploaded_file:
    fingerprint = f"{uploaded_file.name}_{uploaded_file.size}"
    if st.session_state.get("last_uploaded_file") == fingerprint:
        uploaded_file = None
    else:
        st.session_state["last_uploaded_file"] = fingerprint

if uploaded_file:
    progress = st.progress(0, text="Backing up database...")
    backup_path = backup_database()
    progress.progress(10, text="✅ Backup completed. Proceeding with file load. This may take a while...")

    loader = DataLoader(uploaded_file)
    try:
        df_new = loader.load_and_clean()
        calibration_factors = [0.002850975, 0.002861057, 0.002860953, 0.002837607, 0.00291866, 0.00295328, 0.00290534, 0.0029289]
        print(f"\nThe new DF has columns: \n{df_new.columns.tolist()}\nof length: {len(df_new.columns)}")
        print(f"\n And the calibration factors have length: \n{len(calibration_factors)}")
        df_new = loader.compute_channel_differences(df_new, calibration_factors)
    except Exception as e:
        progress.progress(100, text="❌ Error processing file.")
        st.error(f"Error loading file: {e}")
        st.stop()

    progress.progress(40, text="📊 Data cleaned. Checking database for duplicates...")
    latest_dt = db.get_latest_datetime()

    if latest_dt is not None:
        df_new = df_new[df_new['datetime'] > latest_dt]
        st.info(f"🧰 Keeping {len(df_new)} new rows newer than {latest_dt}")
    else:
        st.info("ℹ️ DB empty, keeping all new data")

    progress.progress(70, text="📥 Preparing to insert new records...")

    if df_new.empty:
        progress.progress(100, text="⚠️ No new records to insert.")
    else:
        db.save_to_db(df_new)
        progress.progress(100, text="✅ Upload complete. Data saved.")
        st.success(f"{len(df_new)} new rows added.")
        st.session_state["uploaded_once"] = True
        st.rerun()
