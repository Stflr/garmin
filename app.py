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

# Słownik ładnych nazw i ikon dla sportów (globalny)
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
    tab1, tab2, tab3 = st.tabs(["📍 Mapa Aktywności", "🏆 Moje Najlepsze Wyniki", "📊 Wykres Roczny (Miesiąc po miesiącu)"])
    
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

    # --- ZAKŁADKA 3: WYKRES MIESIĘCZNY DLA WYBRANEGO ROKU ---
    with tab3:
        st.subheader("📈 Dokładny dystans miesiąc po miesiącu w wybranym roku")
        
        # Wyciągamy dostępne lata z aktywności
        years = set()
        for act in st.session_state.activities:
            st_time = act.get('startTimeLocal')
            if st_time and len(st_time) >= 4:
                years.add(st_time[:4])
        
        available_years = sorted(list(years), reverse=True)
        
        if available_years:
            selected_year = st.selectbox("Wybierz rok do analizy:", available_years)
            
            # Filtrujemy aktywności tylko dla wybranego roku
            year_acts = [act for act in st.session_state.activities if act.get('startTimeLocal', '').startswith(selected_year)]
            
            chart_rows = []
            active_sports = set()
            for act in year_acts:
                start_time = act.get('startTimeLocal')
                if start_time and len(start_time) >= 7:
                    month = start_time[5:7]  # Pobieramy numer miesiąca ("01", "02" itd.)
                    type_key = act.get('activityType', {}).get('typeKey', 'inne')
                    distance_m = act.get('distance', 0)
                    distance_km = distance_m / 1000 if distance_m else 0
                    
                    if distance_km > 0:
                        display_name = sport_names.get(type_key, type_key.replace('_', ' ').capitalize())
                        active_sports.add(display_name)
                        chart_rows.append({
                            "Miesiąc_Num": month,
                            "Sport": display_name,
                            "Dystans (km)": distance_km
                        })
            
            if chart_rows:
                df_chart = pd.DataFrame(chart_rows)
                df_grouped = df_chart.groupby(["Miesiąc_Num", "Sport"], as_index=False)["Dystans (km)"].sum()
                
                # Słownik pełnych nazw miesięcy, aby linijka leciała od Stycznia do Grudnia
                months_map = {
                    '01': 'Styczeń', '02': 'Luty', '03': 'Marzec', '04': 'Kwiecień',
                    '05': 'Maj', '06': 'Czerwiec', '07': 'Lipiec', '08': 'Sierpień',
                    '09': 'Wrzesień', '10': 'Październik', '11': 'Listopad', '12': 'Grudzień'
                }
                
                # Budujemy pełną siatkę miesięcy dla każdego sportu (uzupełnienie zerami, żeby linia szła poprawnie)
                full_grid = []
                for sport in active_sports:
                    for m_num, m_name in months_map.items():
                        match = df_grouped[(df_grouped["Miesiąc_Num"] == m_num) & (df_grouped["Sport"] == sport)]
                        dist = match["Dystans (km)"].values[0] if not match.empty else 0.0
                        full_grid.append({
                            "Miesiąc_Num": m_num,
                            "Miesiąc": m_name,
                            "Sport": sport,
                            "Dystans (km)": dist
                        })
                
                df_full = pd.DataFrame(full_grid)
                df_full = df_full.sort_values("Miesiąc_Num")
                
                # Tworzymy wykres liniowy
                fig = px.line(
                    df_full,
                    x="Miesiąc",
                    y="Dystans (km)",
                    color="Sport",
                    markers=True,
                    title=f"Aktywność w roku {selected_year}"
                )
                
                fig.update_layout(
                    xaxis_title="Miesiąc",
                    yaxis_title="Dystans (km)",
                    legend_title="Dyscyplina",
                    hovermode="x unified",
                    xaxis={'categoryorder': 'array', 'categoryarray': list(months_map.values())}
                )
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info(f"Brak danych o dystansie dla roku {selected_year}.")
        else:
            st.info("Brak danych o latach w aktywnościach.")
else:
    st.info("👈 Zaloguj się do Garmina w panelu bocznym, aby uruchomić aplikację.")
