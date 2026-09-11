import streamlit as st
import datetime
import pandas as pd
import streamlit.components.v1 as components
from garminconnect import Garmin
import folium
from folium.plugins import MarkerCluster
import plotly.express as px
import plotly.graph_objects as go

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

# Panel boczny do logowania i narzędzi
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

    # --- EKSPORT DO CSV ---
    if st.session_state.activities:
        st.divider()
        st.subheader("📥 Eksport danych")
        df_export = pd.DataFrame(st.session_state.activities)
        st.download_button(
            label="Pobierz wszystkie aktywności (CSV)",
            data=df_export.to_csv(index=False).encode('utf-8'),
            file_name=f"garmin_activities_{datetime.date.today().isoformat()}.csv",
            mime="text/csv",
            use_container_width=True
        )

if st.session_state.activities:
    today = datetime.date.today().isoformat()
    steps = st.session_state.stats.get('totalSteps', 'Brak')
    rhr = st.session_state.stats.get('restingHeartRate', 'Brak')
    
    # Górne kafelki podsumowujące
    col1, col2 = st.columns(2)
    col1.metric("🚶 Kroki (Dzisiaj)", steps)
    col2.metric("❤️ Tętno spoczynkowe", f"{rhr} bpm" if rhr != 'Brak' else 'Brak')
    
    st.divider()
    
    # Rozbudowane zakładki
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📍 Mapa", 
        "🏆 Wyniki", 
        "📈 Postępy Lat", 
        "🔥 Kalendarz & Tydzień", 
        "❤️ Analiza Formy"
    ])
    
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

    # --- ZAKŁADKA 3: YEAR PROGRESSIONS ---
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
                        normalized_date = dt.replace(year=2024)
                    except:
                        continue
                        
                    distance_km = (act.get('distance') or 0) / 1000
                    if distance_km > 0:
                        daily_records.append({
                            "Year": str(year),
                            "Date": normalized_date,
                            "Distance": distance_km
                        })
            
            if daily_records:
                df_prog = pd.DataFrame(daily_records)
                df_daily_sum = df_prog.groupby(["Year", "Date"], as_index=False)["Distance"].sum()
                
                years_present = sorted(df_daily_sum["Year"].unique())
                date_range = pd.date_range(start="2024-01-01", end="2024-12-31")
                
                full_calendar = []
                for yr in years_present:
                    yr_subset = df_daily_sum[df_daily_sum["Year"] == yr]
                    dict_yr = dict(zip(yr_subset["Date"], yr_subset["Distance"]))
                    
                    running_total = 0.0
                    for d in date_range:
                        if d in dict_yr:
                            running_total += dict_yr[d]
                        full_calendar.append({
                            "Year": yr,
                            "Date": d,
                            "CumulativeDistance": running_total
                        })
                        
                df_final_plot = pd.DataFrame(full_calendar)
                
                fig = px.line(
                    df_final_plot,
                    x="Date",
                    y="CumulativeDistance",
                    color="Year",
                    title="Cumulative Distance in kilometers",
                    labels={"Date": "Miesiąc", "CumulativeDistance": "Łączny dystans (km)", "Year": "Rok"}
                )
                
                fig.update_layout(
                    xaxis=dict(
                        type="date",
                        tickformat="%b",
                        dtick="M1",
                        ticklabelmode="period"
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

    # --- ZAKŁADKA 4: CZYTELNY KALENDARZ AKTYWNOŚCI & PODSUMOWANIA ---
    with tab4:
        st.subheader("📊 Podsumowania okresowe i Kalendarz aktywności")
        
        df_acts = pd.DataFrame(st.session_state.activities)
        if not df_acts.empty and 'startTimeLocal' in df_acts.columns:
            df_acts['DateTime'] = pd.to_datetime(df_acts['startTimeLocal'], errors='coerce')
            df_acts['Date'] = df_acts['DateTime'].dt.date
            df_acts['DistanceKm'] = (df_acts['distance'].fillna(0)) / 1000
            
            # KPI Tygodniowe / Miesięczne
            now = datetime.datetime.now()
            current_week = now.isocalendar()[1]
            current_month = now.month
            current_year = now.year
            
            this_week_dist = df_acts[(df_acts['DateTime'].dt.isocalendar().week == current_week) & (df_acts['DateTime'].dt.year == current_year)]['DistanceKm'].sum()
            last_week_dist = df_acts[(df_acts['DateTime'].dt.isocalendar().week == current_week - 1) & (df_acts['DateTime'].dt.year == current_year)]['DistanceKm'].sum()
            
            this_month_dist = df_acts[(df_acts['DateTime'].dt.month == current_month) & (df_acts['DateTime'].dt.year == current_year)]['DistanceKm'].sum()
            last_month_dist = df_acts[(df_acts['DateTime'].dt.month == current_month - 1) & (df_acts['DateTime'].dt.year == current_year)]['DistanceKm'].sum()
            
            col_a, col_b = st.columns(2)
            with col_a:
                st.metric("🏃 Dystans w tym tygodniu", f"{this_week_dist:.1f} km", delta=f"{this_week_dist - last_week_dist:.1f} km vs pop. tydzień")
            with col_b:
                st.metric("📅 Dystans w tym miesiącu", f"{this_month_dist:.1f} km", delta=f"{this_month_dist - last_month_dist:.1f} km vs pop. miesiąc")
                
            st.divider()
            
            # --- CZYTELNA MAPA CIEPŁA (GITHUB STYLE) ---
            st.markdown("### 🔥 Kalendarz Aktywności (Ostatni rok)")
            
            # Generujemy pełny zakres ostatnich 365 dni, żeby siatka była równa
            end_date = datetime.date.today()
            start_date = end_date - datetime.timedelta(days=365)
            full_date_range = pd.date_range(start=start_date, end=end_date)
            
            df_full = pd.DataFrame({"DateTime": full_date_range})
            df_full['Date'] = df_full['DateTime'].dt.date
            
            # Agregujemy dzienne dystanse z aktywności
            df_daily_agg = df_acts.groupby("Date", as_index=False)["DistanceKm"].sum()
            
            # Łączymy z pełną siatką dni (uzupełniamy zera tam, gdzie nie było treningu)
            df_calendar = pd.merge(df_full, df_daily_agg, on="Date", how="left").fillna(0)
            
            # Wyciągamy pomocnicze kolumny do układu siatki (Tydzień roku i Dzień tygodnia)
            df_calendar['WeekOfYear'] = df_calendar['DateTime'].dt.isocalendar().week
            # Korekta roku, jeśli tydzień 1 przypada na grudzień poprzedniego roku
            df_calendar['Year'] = df_calendar['DateTime'].dt.year
            df_calendar['WeekIndex'] = df_calendar['DateTime'].dt.strftime('%Y-%U')
            
            # Nazwy dni tygodnia po polsku
            day_names_pl = {0: 'Poniedziałek', 1: 'Wtorek', 2: 'Środa', 3: 'Czwartek', 4: 'Piątek', 5: 'Sobota', 6: 'Niedziela'}
            df_calendar['DayOfWeekNum'] = df_calendar['DateTime'].dt.dayofweek
            df_calendar['DayOfWeek'] = df_calendar['DayOfWeekNum'].map(day_names_pl)
            
            # Sortujemy dni od poniedziałku do niedzieli
            df_calendar.sort_values(['Year', 'WeekOfYear', 'DayOfWeekNum'], inplace=True)
            
            # Tworzymy wykres siatkowy (Heatmapa w układzie Tydzień vs Dzień tygodnia)
            fig_heat = px.imshow(
                df_calendar.pivot(index="DayOfWeek", columns="WeekIndex", values="DistanceKm"),
                labels=dict(x="Tydzień roku", y="Dzień tygodnia", color="Dystans (km)"),
                y=['Poniedziałek', 'Wtorek', 'Środa', 'Czwartek', 'Piątek', 'Sobota', 'Niedziela'],
                color_continuous_scale="Greens",
                aspect="auto"
            )
            
            fig_heat.update_layout(
                title="Rozkład treningów dzień po dniu (styl GitHub)",
                xaxis_title="Kolejne tygodnie roku",
                yaxis_title="",
                xaxis=dict(showticklabels=False)  # Ukrywamy numery tygodni, żeby było czysto i estetycznie
            )
            
            st.plotly_chart(fig_heat, use_container_width=True)

    # --- ZAKŁADKA 5: ANALIZA FORMY ---
    with tab5:
        st.subheader("❤️ Analiza tętna i stref wysiłkowych")
        
        df_acts = pd.DataFrame(st.session_state.activities)
        if not df_acts.empty and 'averageHR' in df_acts.columns:
            df_hr = df_acts.dropna(subset=['averageHR', 'startTimeLocal']).copy()
            df_hr['Date'] = pd.to_datetime(df_hr['startTimeLocal']).dt.date
            df_hr['Sport'] = df_hr['activityType'].apply(lambda x: x.get('typeKey') if isinstance(x, dict) else 'Inne')
            
            fig_hr = px.scatter(
                df_hr,
                x="Date",
                y="averageHR",
                color="Sport",
                hover_data=["activityName", "distance"],
                title="Średnie tętno treningów w czasie",
                labels={"Date": "Data", "averageHR": "Średnie tętno (bpm)", "Sport": "Dyscyplina"}
            )
            st.plotly_chart(fig_hr, use_container_width=True)
            
            st.markdown("### 📊 Rozkład średniego tętna wg sportów")
            fig_box = px.box(
                df_hr,
                x="Sport",
                y="averageHR",
                color="Sport",
                title="Rozpiętość tętna dla poszczególnych dyscyplin"
            )
            st.plotly_chart(fig_box, use_container_width=True)
        else:
            st.info("Brak wystarczających danych tętna w pobranym strumieniu aktywności.")

else:
    st.info("👈 Zaloguj się do Garmina w panelu bocznym, aby uruchomić aplikację.")
