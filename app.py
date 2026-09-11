import streamlit as st
import datetime
import pandas as pd
import streamlit.components.v1 as components
from garminconnect import Garmin
import folium
from folium.plugins import MarkerCluster
import plotly.express as px

st.set_page_config(page_title="Moje dane Garmin", page_icon="🏃", layout="wide")

if "activities" not in st.session_state:
    st.session_state.activities = []
if "stats" not in st.session_state:
    st.session_state.stats = {}

st.title("🏃 Garmin Activity Dashboard")

# Słownik ładnych nazw i ikon dla sportów
sport_names = {
    'running': '🏃 Bieganie',
    'cycling': '🚴 Kolarstwo',
    'mountain_biking': '🚵 Kolarstwo górskie',
    'swimming': '🏊 Pływanie',
    'walking': '🚶 Chód',
    'hiking': '🥾 Trekking / Piesze wycieczki',
    'strength_training': '🏋️ Trening siłowy',
    'cardio': '❤️ Cardio',
    'yoga': '🧘 Joga',
    'elliptical': '🔄 Orbitrek',
    'treadmill_running': '🏃‍♂️ Bieg na bieżni'
}

# Panel boczny do logowania
with st.sidebar:
    st.header("🔑 Logowanie Garmin")
    garmin_email = st.text_input("Email Garmin")
    garmin_pass = st.text_input("Hasło Garmin", type="password")

    if st.button("Pobierz dane", type="primary"):
        if not garmin_email or not garmin_pass:
            st.warning("Podaj dane logowania do Garmina.")
        else:
            with st.spinner("Pobieranie historii z Garmina..."):
                try:
                    client = Garmin(garmin_email, garmin_pass)
                    client.login()
                    today = datetime.date.today().isoformat()
                    st.session_state.stats = client.get_stats(today)
                    
                    all_acts = []
                    start = 0
                    limit = 100
                    while True:
                        batch = client.get_activities(start, limit)
                        if not batch:
                            break
                        all_acts.extend(batch)
                        start += limit
                    st.session_state.activities = all_acts
                    st.success("Dane pobrane pomyślnie!")
                except Exception as e:
                    st.error(f"Błąd logowania: {e}")

if st.session_state.activities:
    today = datetime.date.today().isoformat()
    steps = st.session_state.stats.get('totalSteps', 'Brak')
    rhr = st.session_state.stats.get('restingHeartRate', 'Brak')
    
    # Górne kafelki podsumowujące
    col1, col2 = st.columns(2)
    col1.metric("🚶 Kroki (Dzisiaj)", steps)
    col2.metric("❤️ Tętno spoczynkowe", f"{rhr} bpm" if rhr != 'Brak' else 'Brak')
    
    st.divider()
    
    # Trzy zakładki
    tab1, tab2, tab3 = st.tabs(["📍 Mapa Aktywności", "🏆 Moje Najlepsze Wyniki", "📊 Porównanie Lat (Progressions)"])
    
    # --- ZAKŁADKA 1: MAPA ---
    with tab1:
        all_acts = st.session_state.activities
        available_sports = list(set([act.get('activityType', {}).get('typeKey', 'inne') for act in all_acts]))
        available_sports.sort()
        
        with st.container(border=True, height=220):
            st.markdown("### 🎛️ Filtruj sporty na mapie")
            selected_sports = st.multiselect(
                "Wybierz dyscypliny:",
                options=available_sports,
                default=available_sports,
                format_func=lambda x: sport_names.get(x, f"🎯 {x.replace('_', ' ').capitalize()}")
            )
        
        filtered_acts = [act for act in all_acts if act.get('activityType', {}).get('typeKey', 'inne') in selected_sports]
        
        map_data = []
        for act in filtered_acts:
            lat = act.get('startLatitude')
            lon = act.get('startLongitude')
            act_id = act.get('activityId')
            name = act.get('activityName', 'Trening')
            type_key = act.get('activityType', {}).get('typeKey', 'aktywność')
            type_display = sport_names.get(type_key, type_key.capitalize())
            
            if lat and lon and act_id:
                map_data.append({'lat': lat, 'lon': lon, 'id': act_id, 'name': name, 'type': type_display})
                
        if map_data:
            avg_lat = sum([d['lat'] for d in map_data]) / len(map_data)
            avg_lon = sum([d['lon'] for d in map_data]) / len(map_data)
            
            m = folium.Map(location=[avg_lat, avg_lon], zoom_start=6)
            marker_cluster = MarkerCluster().add_to(m)
            
            for d in map_data:
                url = f"https://connect.garmin.com/modern/activity/{d['id']}"
                popup_html = f"<div style='min-width: 150px; font-family: sans-serif;'><b>{d['name']}</b><br><i>{d['type']}</i><br><br><a href='{url}' target='_blank' style='color: #007CC3;'>Otwórz pełną trasę w Garmin ↗️</a></div>"
                folium.Marker(location=[d['lat'], d['lon']], popup=folium.Popup(popup_html, max_width=300), tooltip=d['name']).add_to(marker_cluster)
            
            components.html(m._repr_html_(), height=600)
        else:
            st.info("Brak znaczników GPS dla wybranych sportów.")

    # --- ZAKŁADKA 2: TABLICA WYNIKÓW ---
    with tab2:
        st.subheader("Twoje najszybsze biegi na konkretnych dystansach")
        runs = [a for a in st.session_state.activities if a.get('activityType', {}).get('typeKey') == 'running']
        
        distances = [
            ("5 km", 4.9, 5.2),
            ("10 km", 9.9, 10.3),
            ("Półmaraton", 21.0, 21.3),
            ("Maraton", 42.1, 42.6)
        ]
        
        records_data = []
        for name, min_dist, max_dist in distances:
            valid_runs = [r for r in runs if min_dist <= (r.get('distance', 0)/1000) <= max_dist]
            if valid_runs:
                best_run = min(valid_runs, key=lambda x: x.get('duration', float('inf')))
                duration_sec = best_run.get('duration', 0)
                time_str = str(datetime.timedelta(seconds=int(duration_sec)))
                avg_pace_sec = duration_sec / (best_run.get('distance', 1)/1000)
                pace_min = int(avg_pace_sec // 60)
                pace_sec = int(avg_pace_sec % 60)
                act_id = best_run.get('activityId')
                
                records_data.append({
                    "Dystans": name,
                    "Czas": time_str,
                    "Śr. Tempo": f"{pace_min}:{pace_sec:02d} /km",
                    "Nazwa": best_run.get('activityName', 'Bieg'),
                    "Data": best_run.get('startTimeLocal', '')[:10],
                    "Link": f"https://connect.garmin.com/modern/activity/{act_id}" if act_id else None
                })
            else:
                records_data.append({"Dystans": name, "Czas": "Brak danych", "Śr. Tempo": "-", "Nazwa": "-", "Data": "-", "Link": None})
                
        df_records = pd.DataFrame(records_data)
        st.dataframe(
            df_records,
            column_config={
                "Link": st.column_config.LinkColumn("Aktywność", display_text="Otwórz w Garmin ↗️")
            },
            use_container_width=True,
            hide_index=True
        )

    # --- ZAKŁADKA 3: YEAR PROGRESSIONS (CIĄGŁY WYKRES) ---
    with tab3:
        st.subheader("📈 Cumulative Distance Progressions")
        
        all_sport_keys = list(set([act.get('activityType', {}).get('typeKey', 'inne') for act in st.session_state.activities]))
        selected_chart_sports = st.multiselect(
            "Filtruj sporty do wykresu postępów:",
            options=all_sport_keys,
            default=all_sport_keys,
            format_func=lambda x: sport_names.get(x, f"🎯 {x.replace('_', ' ').capitalize()}")
        )
        
        filtered_progress_acts = [
            act for act in st.session_state.activities 
            if act.get('activityType', {}).get('typeKey', 'inne') in selected_chart_sports
        ]
        
        if filtered_progress_acts:
            daily_records = []
            for act in filtered_progress_acts:
                st_time = act.get('startTimeLocal')
                if st_time and len(st_time) >= 10:
                    date_str = st_time[:10]
                    year = date_str[:4]
                    try:
                        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                        normalized_date = dt.replace(year=2024).strftime("%m-%d")
                    except:
                        continue
                        
                    distance_km = (act.get('distance') or 0) / 1000
                    if distance_km > 0:
                        daily_records.append({
                            "Year": str(year),
                            "NormalizedDate": normalized_date,
                            "Distance": distance_km
                        })
            
            if daily_records:
                df_prog = pd.DataFrame(daily_records)
                df_daily_sum = df_prog.groupby(["Year", "NormalizedDate"], as_index=False)["Distance"].sum()
                
                years_present = sorted(df_daily_sum["Year"].unique())
                date_range = pd.date_range(start="2024-01-01", end="2024-12-31").strftime("%m-%d").tolist()
                
                full_calendar = []
                for yr in years_present:
                    yr_subset = df_daily_sum[df_daily_sum["Year"] == yr]
                    dict_yr = dict(zip(yr_subset["NormalizedDate"], yr_subset["Distance"]))
                    
                    running_total = 0.0
                    for d in date_range:
                        if d in dict_yr:
                            running_total += dict_yr[d]  # Sumujemy narastająco każdy dzień
                        full_calendar.append({
                            "Year": yr,
                            "NormalizedDate": d,
                            "CumulativeDistance": running_total
                        })
                        
                df_final_plot = pd.DataFrame(full_calendar)
                
                fig = px.line(
                    df_final_plot,
                    x="NormalizedDate",
                    y="CumulativeDistance",
                    color="Year",
                    title="Cumulative Distance in kilometers",
                    labels={"NormalizedDate": "Dzień roku", "CumulativeDistance": "Łączny dystans (km)", "Year": "Rok"}
                )
                
                month_ticks = ["01-01", "02-01", "03-01", "04-01", "05-01", "06-01", "07-01", "08-01", "09-01", "10-01", "11-01", "12-01"]
                month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                
                fig.update_layout(
                    xaxis=dict(
                        tickmode="array",
                        tickvals=month_ticks,
                        ticktext=month_labels,
                        title=""
                    ),
                    yaxis_title="Cumulative Distance (km)",
                    hovermode="x unified",
                    legend_title="Years"
                )
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Brak wystarczających danych o dystansie do zbudowania wykresów.")
        else:
            st.info("Zaznacz przynajmniej jeden sport w filtrze powyżej.")
else:
    st.info("👈 Zaloguj się do Garmina w panelu bocznym, aby uruchomić aplikację.")
