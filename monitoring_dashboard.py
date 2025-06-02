import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time
import os
import plotly.express as px
import plotly.graph_objects as go

# Set page config
st.set_page_config(
    page_title="Parking System Monitor",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for improved styling
st.markdown("""
    <style>
    .main {
        padding: 2rem;
        background-color: #f8f9fa;
    }
    .stMetric {
        background-color: #ffffff;
        padding: 1.5rem;
        border-radius: 0.75rem;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        border: 1px solid #e0e0e0;
    }
    .stAlert {
        padding: 1rem;
        border-radius: 0.75rem;
        background-color: #fff5f5;
        border: 1px solid #f87171;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 1.5rem;
        background-color: #f0f2f6;
        padding: 0.5rem;
        border-radius: 0.75rem;
    }
    .stTabs [data-baseweb="tab"] {
        height: 3.5rem;
        white-space: pre-wrap;
        background-color: #e0e0e0;
        border-radius: 0.5rem;
        padding: 1rem;
        font-weight: 600;
        color: #2563eb;
    }
    .stTabs [aria-selected="true"] {
        background-color: #2563eb;
        color: #ffffff;
        border-radius: 0.5rem;
    }
    .card {
        background-color: #ffffff;
        padding: 1.5rem;
        border-radius: 0.75rem;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        margin-bottom: 1.5rem;
    }
    </style>
""", unsafe_allow_html=True)

def load_unauthorised():
    try:
        unauthorised = pd.read_csv("database/unauthorized_exits.csv")
        unauthorised['Timestamp'] = pd.to_datetime(unauthorised['Timestamp'])
        return unauthorised
    except Exception as e:
        st.error(f"Error loading unauthorised data: {str(e)}")
        return None

def load_data():
    """Load data from CSV files"""
    try:
        plates_log = pd.read_csv("database/plates_log.csv")
        plates_log["status"] = plates_log["Out time"].apply(
            lambda x: "out" if pd.notna(x) and x != "" else "in"
        )
        plates_log["In time"] = pd.to_datetime(plates_log["In time"])
        plates_log["Out time"] = pd.to_datetime(plates_log["Out time"], errors='coerce')
        return plates_log
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return None

def calculate_duration(row):
    if pd.notna(row["Out time"]):
        return (row["Out time"] - row["In time"]).total_seconds() / 3600
    return None

def main():
    st.title("🚗 Parking System Monitor")

    # Sidebar
    with st.sidebar:
        st.image("https://img.icons8.com/color/48/000000/car.png", width=48)
        st.header("Filters")
        with st.expander("Date & Refresh Settings", expanded=True):
            date_range = st.date_input(
                "Select Date Range",
                value=(datetime.now() - timedelta(days=7), datetime.now()),
                max_value=datetime.now(),
                help="Filter data by entry date range"
            )
            auto_refresh = st.checkbox("Auto-Refresh (every 10s)", value=True)
        st.markdown("---")
        st.caption("Last updated: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    # Create tabs
    tab1, tab2, tab3, tab4 = st.tabs(
        ["Real-time Monitoring", "Unauthorized Exits", "Vehicle History", "Analytics"]
    )

    with tab1:
        st.header("Real-time Vehicle Monitoring")
        with st.container():
            st.markdown('<div class="card">', unsafe_allow_html=True)
            col1, col2, col3, col4 = st.columns(4)

            # Load data with spinner
            with st.spinner("Loading data..."):
                plates_log = load_data()
                unauthorised = load_unauthorised()

            if plates_log is not None:
                # Calculate metrics
                total_vehicles = len(plates_log)
                current_vehicles = len(plates_log[plates_log["status"] == "in"])
                unauthorized_exits = len(unauthorised) if unauthorised is not None else 0
                plates_log["duration"] = plates_log.apply(calculate_duration, axis=1)
                avg_duration = plates_log["duration"].mean()

                with col1:
                    delta = total_vehicles - len(plates_log[plates_log['In time'] < pd.Timestamp(date_range[0])])
                    st.metric("Total Vehicles", total_vehicles, delta=f"{delta}", delta_color="normal")
                with col2:
                    st.metric("Current Vehicles", current_vehicles, delta_color="off")
                with col3:
                    st.metric("Unauthorized Exits", unauthorized_exits, delta_color="normal")
                with col4:
                    st.metric("Avg. Duration (hrs)", f"{avg_duration:.2f}", delta_color="off")
            st.markdown('</div>', unsafe_allow_html=True)

            # Recent activity
            st.subheader("Recent Activity")
            with st.container():
                st.markdown('<div class="card">', unsafe_allow_html=True)
                if plates_log is not None:
                    recent_activity = plates_log.sort_values(by="In time", ascending=False).head(10)
                    styled_df = recent_activity.style.format({
                        "In time": lambda x: x.strftime("%Y-%m-%d %H:%M:%S"),
                        "Out time": lambda x: x.strftime("%Y-%m-%d %H:%M:%S") if pd.notna(x) else "N/A"
                    }).applymap(
                        lambda x: 'background-color: #dcfce7; color: #166534;' if x == "in" 
                        else 'background-color: #fee2e2; color: #991b1b;', 
                        subset=["status"]
                    )
                    st.dataframe(styled_df, use_container_width=True, height=350)
                    if st.button("Export Recent Activity to CSV"):
                        recent_activity.to_csv("recent_activity_export.csv", index=False)
                        st.success("Exported successfully!")
                st.markdown('</div>', unsafe_allow_html=True)

    with tab2:
        st.header("Unauthorized Exit Attempts")
        with st.container():
            st.markdown('<div class="card">', unsafe_allow_html=True)
            if unauthorised is not None and not unauthorised.empty:
                st.dataframe(unauthorised, use_container_width=True, height=350)
                daily_counts = unauthorised.groupby(unauthorised['Timestamp'].dt.date).size().reset_index(name='count')
                fig = px.bar(
                    daily_counts,
                    x='Timestamp',
                    y='count',
                    title='Unauthorized Exits Over Time',
                    labels={'Timestamp': 'Date', 'count': 'Number of Unauthorized Exits'},
                    color_discrete_sequence=['#dc2626']  # Bright red
                )
                fig.update_layout(
                    showlegend=False,
                    hovermode='x unified',
                    plot_bgcolor='white',
                    paper_bgcolor='white',
                    xaxis=dict(
                        gridcolor='#e5e7eb',
                        showgrid=True
                    ),
                    yaxis=dict(
                        gridcolor='#e5e7eb',
                        showgrid=True
                    )
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.markdown('<div class="stAlert">No unauthorized exit attempts recorded. ✅</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

    with tab3:
        st.header("Vehicle History")
        with st.container():
            st.markdown('<div class="card">', unsafe_allow_html=True)
            if plates_log is not None:
                # Filters
                with st.expander("Filter Settings", expanded=True):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        plate_filter = st.text_input("Filter by Plate Number", help="Search by partial plate number")
                    with col2:
                        status_filter = st.selectbox("Filter by Status", ["All"] + list(plates_log["status"].unique()))
                    with col3:
                        duration_filter = st.slider("Min Duration (hrs)", 0.0, 24.0, 0.0, 0.5)
                    if st.button("Reset Filters"):
                        plate_filter, status_filter, duration_filter = "", "All", 0.0

                # Apply filters
                filtered_data = plates_log
                if plate_filter:
                    filtered_data = filtered_data[filtered_data["Plate Number"].str.contains(plate_filter, case=False, na=False)]
                if status_filter != "All":
                    filtered_data = filtered_data[filtered_data["status"] == status_filter]
                if duration_filter > 0:
                    filtered_data = filtered_data[filtered_data["duration"] >= duration_filter]

                styled_df = filtered_data.style.format({
                    "In time": lambda x: x.strftime("%Y-%m-%d %H:%M:%S"),
                    "Out time": lambda x: x.strftime("%Y-%m-%d %H:%M:%S") if pd.notna(x) else "N/A",
                    "duration": lambda x: f"{x:.2f} hrs" if pd.notna(x) else "N/A"
                }).applymap(
                    lambda x: 'background-color: #dcfce7; color: #166534;' if x == "in" 
                    else 'background-color: #fee2e2; color: #991b1b;', 
                    subset=["status"]
                )
                st.dataframe(styled_df, use_container_width=True, height=350)
                if st.button("Export History to CSV"):
                    filtered_data.to_csv("vehicle_history_export.csv", index=False)
                    st.success("Exported successfully!")
            st.markdown('</div>', unsafe_allow_html=True)

    with tab4:
        st.header("Analytics Dashboard")
        with st.container():
            st.markdown('<div class="card">', unsafe_allow_html=True)
            if plates_log is not None:
                col1, col2 = st.columns(2)
                with col1:
                    hourly_data = plates_log.groupby(plates_log['In time'].dt.hour).size()
                    fig1 = px.line(
                        x=hourly_data.index,
                        y=hourly_data.values,
                        title='Vehicle Occupancy by Hour',
                        labels={'x': 'Hour of Day', 'y': 'Number of Vehicles'},
                        color_discrete_sequence=['#2563eb']  # Bright blue
                    )
                    fig1.update_layout(
                        showlegend=False,
                        hovermode='x unified',
                        plot_bgcolor='white',
                        paper_bgcolor='white',
                        xaxis=dict(
                            gridcolor='#e5e7eb',
                            showgrid=True
                        ),
                        yaxis=dict(
                            gridcolor='#e5e7eb',
                            showgrid=True
                        )
                    )
                    st.plotly_chart(fig1, use_container_width=True)

                with col2:
                    fig2 = px.histogram(
                        plates_log,
                        x='duration',
                        title='Parking Duration Distribution',
                        labels={'duration': 'Duration (hours)', 'count': 'Count'},
                        color_discrete_sequence=['#059669']  # Emerald green
                    )
                    fig2.update_layout(
                        showlegend=False,
                        hovermode='x unified',
                        plot_bgcolor='white',
                        paper_bgcolor='white',
                        xaxis=dict(
                            gridcolor='#e5e7eb',
                            showgrid=True
                        ),
                        yaxis=dict(
                            gridcolor='#e5e7eb',
                            showgrid=True
                        )
                    )
                    st.plotly_chart(fig2, use_container_width=True)

                st.subheader("Key Performance Indicators")
                col1, col2, col3 = st.columns(3)
                with col1:
                    peak_hour = hourly_data.idxmax()
                    st.metric("Peak Hour", f"{peak_hour:02d}:00")
                with col2:
                    avg_daily_vehicles = len(plates_log) / max((date_range[1] - date_range[0]).days, 1)
                    st.metric("Avg. Daily Vehicles", f"{avg_daily_vehicles:.1f}")
                with col3:
                    occupancy_rate = (current_vehicles / total_vehicles) * 100 if total_vehicles > 0 else 0
                    st.metric("Current Occupancy Rate", f"{occupancy_rate:.1f}%")
            st.markdown('</div>', unsafe_allow_html=True)

    # Auto-refresh logic
    if auto_refresh:
        time.sleep(10)
        st.rerun()

if __name__ == "__main__":
    main()