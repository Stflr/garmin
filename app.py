import streamlit as st
import datetime
import pandas as pd
import streamlit.components.v1 as components
from garminconnect import Garmin
import folium
from folium.plugins import MarkerCluster
import plotly.express as px
import plotly.graph_objects as go
import calendar

st.set_page_config(page_title="Moje dane Garmin", page_icon="🏃", layout="wide")

if "activities" not in st.session_state:
    st.session_state.activities = []
if "stats" not in st.session_state:
    st.session_state.stats = {}
if "client" not in st.session_state:
    st.session_state.client = None

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
                    st.session_state.client = client
                    
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

    # --- ODŚWIEŻANIE DZISIEJSZYCH KROKÓW ---
    if st.session_state.client:
        st.divider()
        if st.button("🔄 Odśwież dzisiejsze kroki"):
            with st.spinner("Pobieranie aktualnych kroków..."):
                try:
                    today = datetime.date.today().isoformat()
                    st.session_state.stats = st.session_state.client.get_stats(today)
                    st.success("Dzisiejsze statystyki zaktualizowane!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Nie udało się odświeżyć: {e}")

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
    
    # Rozbudowane zakładki (dodana zakładka z listą aktywności na końcu)
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "📍 Mapa", 
        "🏆 Wyniki", 
        "📈 Postępy Lat", 
        "📊 Tygodniowy Kilometraż",
        "🔥 Kalendarz Miesięczny", 
        "❤️ Analiza Formy",
        "📋 Lista Aktywności"
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

    # --- ZAKŁADKA 4: TYGODNIOWY KILOMETRAŻ ---
    with tab4:
        st.subheader("📊 Wykres Tygodniowego Kilometrażu (Objętość Treningowa)")
        
        df_acts = pd.DataFrame(st.session_state.activities)
        if not df_acts.empty and 'startTimeLocal' in df_acts.columns:
            df_acts['DateTime'] = pd.to_datetime(df_acts['startTimeLocal'], errors='coerce')
            df_acts['DistanceKm'] = (df_acts['distance'].fillna(0)) / 1000
            df_acts['DurationSec'] = df_acts['duration'].fillna(0)
            df_acts['SportKey'] = df_acts['activityType'].apply(lambda x: x.get('typeKey', 'Inne') if isinstance(x, dict) else 'Inne')
            
            col_w1, col_w2 = st.columns([2, 2])
            with col_w1:
                weekly_sport_option = st.selectbox(
                    "Wybierz dyscyplinę do wykresu tygodniowego:",
                    options=['all', 'running', 'cycling'],
                    format_func=lambda x: {
                        'all': '🌟 Wszystkie sporty', 
                        'running': '🏃 Tylko bieganie', 
                        'cycling': '🚴 Tylko kolarstwo'
                    }[x],
                    key="weekly_sport_filter"
                )
            with col_w2:
                time_range_option = st.selectbox(
                    "Okres wstecz:",
                    options=[12, 26, 52, 104, 999],
                    format_func=lambda x: {
                        12: 'Ostatnie 3 miesiące (12 tyg.)',
                        26: 'Ostatnie pół roku (26 tyg.)',
                        52: 'Ostatni rok (52 tyg.)',
                        104: 'Ostatnie 2 lata (104 tyg.)',
                        999: 'Cała historia'
                    }[x],
                    key="weekly_range_filter"
                )
            
            if weekly_sport_option == 'running':
                df_w = df_acts[df_acts['SportKey'].isin(['running', 'treadmill_running'])].copy()
            elif weekly_sport_option == 'cycling':
                df_w = df_acts[df_acts['SportKey'].isin(['cycling', 'mountain_biking'])].copy()
            else:
                df_w = df_acts.copy()
                
            if not df_w.empty:
                df_w['WeekStart'] = df_w['DateTime'] - pd.to_timedelta(df_w['DateTime'].dt.weekday, unit='d')
                df_w['WeekStart'] = df_w['WeekStart'].dt.date
                df_w['WeekEnd'] = df_w['WeekStart'] + pd.Timedelta(days=6)
                
                weekly_grouped = df_w.groupby(['WeekStart', 'WeekEnd']).agg(
                    TotalDistance=('DistanceKm', 'sum'),
                    ActivityCount=('activityId', 'count'),
                    TotalDuration=('DurationSec', 'sum')
                ).reset_index()
                
                weekly_grouped = weekly_grouped.sort_values('WeekStart')
                
                if time_range_option != 999 and len(weekly_grouped) > time_range_option:
                    weekly_grouped = weekly_grouped.tail(time_range_option)
                
                weekly_grouped['WeekLabel'] = weekly_grouped.apply(
                    lambda row: f"{row['WeekStart'].strftime('%d.%m')} – {row['WeekEnd'].strftime('%d.%m.%Y')}", axis=1
                )
                
                fig_weekly = px.bar(
                    weekly_grouped,
                    x='WeekLabel',
                    y='TotalDistance',
                    title="Suma dystansu w poszczególnych tygodniach",
                    labels={'WeekLabel': 'Zakres tygodnia', 'TotalDistance': 'Dystans (km)'},
                    text_auto='.1f'
                )
                
                fig_weekly.update_traces(marker_color='#0068c9', textposition='outside')
                fig_weekly.update_layout(
                    xaxis=dict(type='category'),
                    yaxis_title="Dystans (km)",
                    hovermode="x unified"
                )
                
                st.plotly_chart(fig_weekly, use_container_width=True)
                
                with st.expander("📋 Zobacz szczegółową tabelę tygodniową"):
                    display_table = weekly_grouped[['WeekLabel', 'TotalDistance', 'ActivityCount']].copy()
                    display_table.columns = ['Zakres tygodnia', 'Dystans (km)', 'Liczba treningów']
                    display_table['Dystans (km)'] = display_table['Dystans (km)'].round(2)
                    st.dataframe(display_table.sort_values('Zakres tygodnia', ascending=False), use_container_width=True, hide_index=True)
            else:
                st.info("Brak aktywności spełniających wybrane kryteria.")
        else:
            st.info("Brak danych aktywności.")

    # --- ZAKŁADKA 5: KALENDARZ MIESIĘCZNY + PODSUMOWANIE TYGODNIOWE ---
    with tab5:
        st.subheader("📅 Kalendarz Aktywności Miesięcznej i Podsumowania")
        
        df_acts = pd.DataFrame(st.session_state.activities)
        if not df_acts.empty and 'startTimeLocal' in df_acts.columns:
            df_acts['DateTime'] = pd.to_datetime(df_acts['startTimeLocal'], errors='coerce')
            df_acts['Date'] = df_acts['DateTime'].dt.date
            df_acts['Year'] = df_acts['DateTime'].dt.year
            df_acts['Month'] = df_acts['DateTime'].dt.month
            df_acts['DistanceKm'] = (df_acts['distance'].fillna(0)) / 1000
            df_acts['DurationSec'] = df_acts['duration'].fillna(0)
            df_acts['SportKey'] = df_acts['activityType'].apply(lambda x: x.get('typeKey', 'Inne') if isinstance(x, dict) else 'Inne')
            df_acts['SportName'] = df_acts['SportKey'].map(lambda k: sport_names.get(k, k.replace('_', ' ').capitalize()))
            
            available_years = sorted(df_acts['Year'].dropna().unique(), reverse=True)
            if available_years:
                col_sel1, col_sel2, col_sel3 = st.columns(3)
                with col_sel1:
                    sel_year = st.selectbox("Wybierz rok:", available_years, key="cal_year")
                with col_sel2:
                    months_pl = {
                        1: 'Styczeń', 2: 'Luty', 3: 'Marzec', 4: 'Kwiecień',
                        5: 'Maj', 6: 'Czerwiec', 7: 'Lipiec', 8: 'Sierpień',
                        9: 'Wrzesień', 10: 'Październik', 11: 'Listopad', 12: 'Grudzień'
                    }
                    sel_month = st.selectbox("Wybierz miesiąc:", options=list(months_pl.keys()), format_func=lambda x: months_pl[x], key="cal_month")
                with col_sel3:
                    stat_sport_option = st.selectbox(
                        "Dystans do podsumowania:",
                        options=['all', 'running', 'cycling'],
                        format_func=lambda x: {
                            'all': '🌟 Wszystkie sporty', 
                            'running': '🏃 Tylko bieganie', 
                            'cycling': '🚴 Tylko kolarstwo'
                        }[x],
                        key="stat_sport_filter"
                    )
                
                st.divider()
                
                if stat_sport_option == 'running':
                    df_stat_acts = df_acts[df_acts['SportKey'].isin(['running', 'treadmill_running'])]
                elif stat_sport_option == 'cycling':
                    df_stat_acts = df_acts[df_acts['SportKey'].isin(['cycling', 'mountain_biking'])]
                else:
                    df_stat_acts = df_acts
                
                current_month_acts = df_stat_acts[(df_stat_acts['Year'] == sel_year) & (df_stat_acts['Month'] == sel_month)]
                current_month_dist = current_month_acts['DistanceKm'].sum()
                
                prev_year = sel_year - 1
                prev_month_acts = df_stat_acts[(df_stat_acts['Year'] == prev_year) & (df_stat_acts['Month'] == sel_month)]
                prev_month_dist = prev_month_acts['DistanceKm'].sum()
                month_diff = current_month_dist - prev_month_dist
                
                current_year_acts = df_stat_acts[df_stat_acts['Year'] == sel_year]
                current_year_dist = current_year_acts['DistanceKm'].sum()
                
                prev_year_acts = df_stat_acts[df_stat_acts['Year'] == prev_year]
                prev_year_dist = prev_year_acts['DistanceKm'].sum()
                year_diff = current_year_dist - prev_year_dist
                
                m_col1, m_col2 = st.columns(2)
                with m_col1:
                    st.metric(
                        label=f"Dystans w {months_pl[sel_month]} {sel_year}",
                        value=f"{current_month_dist:.1f} km",
                        delta=f"{month_diff:+.1f} km vs {prev_year}" if not prev_month_acts.empty else f"Brak danych z {prev_year}"
                    )
                with m_col2:
                    st.metric(
                        label=f"Cały rok {sel_year} (ogółem)",
                        value=f"{current_year_dist:.1f} km",
                        delta=f"{year_diff:+.1f} km vs {prev_year}" if not prev_year_acts.empty else f"Brak danych z {prev_year}"
                    )
                
                st.divider()

                st.markdown(f"### 📊 Podsumowanie tygodniowe w {months_pl[sel_month]} {sel_year}")
                if not current_month_acts.empty:
                    current_month_acts = current_month_acts.copy()
                    weekly_summary = []
                    cal = calendar.Calendar(firstweekday=0)
                    month_weeks = cal.monthdatescalendar(sel_year, sel_month)
                    
                    for i, w in enumerate(month_weeks, 1):
                        w_start = w[0]
                        w_end = w[-1]
                        w_acts = current_month_acts[(current_month_acts['Date'] >= w_start) & (current_month_acts['Date'] <= w_end)]
                        
                        w_dist = w_acts['DistanceKm'].sum()
                        w_count = len(w_acts)
                        w_duration_sec = w_acts['DurationSec'].sum()
                        w_hours = int(w_duration_sec // 3600)
                        w_mins = int((w_duration_sec % 3600) // 60)
                        w_time_str = f"{w_hours}h {w_mins}m" if w_hours > 0 else f"{w_mins}m"
                        
                        weekly_summary.append({
                            "Tydzień": f"Tydzień {i} ({w_start.strftime('%d.%m')} - {w_end.strftime('%d.%m')})",
                            "Liczba treningów": w_count,
                            "Dystans (km)": round(w_dist, 2),
                            "Czas trwania": w_time_str if w_count > 0 else "-"
                        })
                    
                    df_weekly = pd.DataFrame(weekly_summary)
                    st.dataframe(df_weekly, use_container_width=True, hide_index=True)
                else:
                    st.info("Brak aktywności spełniających kryteria w wybranym miesiącu.")
                
                st.divider()
                
                calendar_month_acts = df_acts[(df_acts['Year'] == sel_year) & (df_acts['Month'] == sel_month)]
                
                cal = calendar.Calendar(firstweekday=0)
                month_days = cal.monthdayscalendar(sel_year, sel_month)
                
                sport_colors = {
                    'running': '#ff4b4b',
                    'cycling': '#0068c9',
                    'mountain_biking': '#83c9ff',
                    'swimming': '#29b09d',
                    'walking': '#ff8700',
                    'hiking': '#7d38df',
                    'strength_training': '#ff2b2b',
                    'cardio': '#eb34db',
                    'yoga': '#34ebd0',
                    'Inne': '#808080'
                }
                
                days_header = ["Poniedziałek", "Wtorek", "Środa", "Czwartek", "Piątek", "Sobota", "Niedziela"]
                
                html_code = f"""
                <div style="font-family: sans-serif; background-color: #0e1117; color: #ffffff; padding: 5px; border-radius: 10px;">
                    <h3 style="text-align: center; color: #ffffff; margin-bottom: 15px;">{months_pl[sel_month]} {sel_year}</h3>
                    <table style="width: 100%; border-collapse: collapse; table-layout: fixed;">
                        <thead>
                            <tr>
                """
                for dh in days_header:
                    html_code += f"<th style='padding: 8px; border: 1px solid #30333b; background-color: #1f242d; color: #9fa6b2; text-align: center; font-size: 13px;'>{dh}</th>"
                html_code += "</tr></thead><tbody>"
                
                for week in month_days:
                    html_code += "<tr>"
                    for day in week:
                        if day == 0:
                            html_code += "<td style='height: 85px; border: 1px solid #30333b; background-color: #161920; opacity: 0.3;'></td>"
                        else:
                            current_date = datetime.date(sel_year, sel_month, day)
                            day_data = calendar_month_acts[calendar_month_acts['Date'] == current_date]
                            
                            cell_bg = "#1f242d"
                            content = f"<div style='font-weight: bold; font-size: 12px; color: #ffffff; margin-bottom: 2px;'>{day}</div>"
                            
                            if not day_data.empty:
                                main_sport = day_data.iloc[0]['SportKey']
                                cell_bg = sport_colors.get(main_sport, '#00cc66')
                                
                                for _, act_row in day_data.iterrows():
                                    sport_label = act_row['SportName']
                                    dist = act_row['DistanceKm']
                                    act_id = act_row.get('activityId')
                                    
                                    if act_id:
                                        garmin_url = f"https://connect.garmin.com/modern/activity/{act_id}"
                                        content += f"<div style='font-size: 9px; background: rgba(0,0,0,0.35); padding: 2px 3px; border-radius: 3px; margin-top: 2px; line-height: 1.1;'>" \
                                                   f"<span style='color: #ffffff;'>{sport_label}</span><br>" \
                                                   f"<b>{dist:.1f} km</b><br>" \
                                                   f"<a href='{garmin_url}' target='_blank' style='color: #ffffff; text-decoration: underline; font-weight: bold;'>🔗 Garmin</a>" \
                                                   f"</div>"
                                    else:
                                        content += f"<div style='font-size: 9px; background: rgba(0,0,0,0.35); padding: 2px; border-radius: 3px; margin-top: 2px;'>{sport_label}<br><b>{dist:.1f} km</b></div>"
                            
                            html_code += f"<td style='height: 85px; border: 1px solid #30333b; background-color: {cell_bg}; vertical-align: top; padding: 4px; text-align: left; overflow: hidden;'>{content}</td>"
                    html_code += "</tr>"
                
                html_code += "</tbody></table></div>"
                
                components.html(html_code, height=560)
            else:
                st.info("Brak dat w aktywnościach.")

    # --- ZAKŁADKA 6: ANALIZA FORMY ---
    with tab6:
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

    # --- ZAKŁADKA 7: LISTA AKTYWNOŚCI (NOWOŚĆ) ---
    with tab7:
        st.subheader("📋 Pełna lista wszystkich aktywności")
        
        df_acts = pd.DataFrame(st.session_state.activities)
        if not df_acts.empty and 'startTimeLocal' in df_acts.columns:
            df_list = df_acts.copy()
            df_list['Data i czas'] = pd.to_datetime(df_list['startTimeLocal'], errors='coerce').dt.strftime('%Y-%m-%d %H:%M')
            df_list['Nazwa'] = df_list['activityName'].fillna('Trening')
            df_list['Sport'] = df_list['activityType'].apply(lambda x: sport_names.get(x.get('typeKey'), x.get('typeKey', 'Inne').replace('_', ' ').capitalize()) if isinstance(x, dict) else 'Inne')
            df_list['Dystans (km)'] = (df_list['distance'].fillna(0) / 1000).round(2)
            
            # Formatowanie czasu trwania z sekund na format HH:MM:SS lub MM:SS
            def format_duration(sec):
                if pd.isna(sec) or sec == 0:
                    return "-"
                td = datetime.timedelta(seconds=int(sec))
                return str(td)
            
            df_list['Czas trwania'] = df_list['duration'].apply(format_duration)
            df_list['Link'] = df_list['activityId'].apply(lambda x: f"https://connect.garmin.com/modern/activity/{x}" if pd.notna(x) else None)
            
            # Wybór i zmiana kolejności kolumn do wyświetlenia
            df_table_final = df_list[['Data i czas', 'Nazwa', 'Sport', 'Dystans (km)', 'Czas trwania', 'Link']].copy()
            df_table_final = df_table_final.sort_values('Data i czas', ascending=False)
            
            st.dataframe(
                df_table_final,
                column_config={
                    "Link": st.column_config.LinkColumn("Garmin Connect", display_text="Otwórz ↗️")
                },
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("Brak danych aktywności do wyświetlenia.")

else:
    st.info("👈 Zaloguj się do Garmina w panelu bocznym, aby uruchomić aplikację.")
