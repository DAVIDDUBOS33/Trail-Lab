import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from urllib.parse import urlencode

# --- CONFIGURATION API (À REMPLIR) ---
CLIENT_ID = "VOTRE_CLIENT_ID"
CLIENT_SECRET = "VOTRE_CLIENT_SECRET"
# L'URL de votre application déployée (ex: https://mon-trail-app.streamlit.app/)
REDIRECT_URI = "https://trail-lab.streamlit.app/" 

st.set_page_config(page_title="Expert Trail Predictor", layout="wide")

# CSS pour masquer le menu Streamlit et s'intégrer proprement dans WordPress
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stApp {background-color: transparent;}
    </style>
    """, unsafe_allow_html=True)

# --- FONCTIONS TECHNIQUES ---

def get_weather_impact(lat, lon):
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        res = requests.get(url).json()
        temp = res['current_weather']['temperature']
        w_code = res['current_weather']['weathercode']
        impact = 1.0
        if temp > 25: impact += (temp - 25) * 0.012  # +1.2% par degré > 25°C
        if w_code > 50: impact += 0.12 # +12% si pluie/neige (terrain gras)
        return impact, temp, w_code
    except:
        return 1.0, 20.0, 0

def get_strava_data(code):
    res = requests.post("https://www.strava.com/oauth/token", data={
        'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET,
        'code': code, 'grant_type': 'authorization_code'
    }).json()
    access_token = res.get('access_token')
    activities = requests.get("https://www.strava.com/api/v3/athlete/activities", 
                             headers={'Authorization': f'Bearer {access_token}'},
                             params={'per_page': 15}).json()
    return activities

# --- INTERFACE UTILISATEUR ---

st.title("🏃‍♂️ Trail Time Predictor Pro")
st.write("Estimez votre chrono en couplant vos données Strava et la météo réelle.")

# Gestion Auth Strava
query_params = st.query_params
if "code" not in query_params:
    auth_params = {"client_id": CLIENT_ID, "redirect_uri": REDIRECT_URI, 
                   "response_type": "code", "scope": "activity:read_all"}
    auth_url = f"https://www.strava.com/oauth/authorize?{urlencode(auth_params)}"
    st.link_button("🔑 Connecter mon compte Strava", auth_url, type="primary")
    # Valeurs par défaut si non connecté
    avg_pace = 6.0 
else:
    with st.spinner('Analyse de votre profil Strava...'):
        activities = get_strava_data(query_params["code"])
        trails = [a for a in activities if a['type'] in ['TrailRun', 'Run']]
        if trails:
            total_dist = sum([a['distance'] for a in trails]) / 1000
            total_time = sum([a['moving_time'] for a in trails]) / 60
            avg_pace = total_time / total_dist
            st.success(f"Données synchronisées ! Allure de base détectée : {avg_pace:.2f} min/km")
        else:
            avg_pace = 6.0
            st.warning("Aucune course trouvée. Utilisation d'une allure par défaut (6:00 min/km).")

st.divider()

# Formulaire Course
col1, col2 = st.columns(2)
with col1:
    st.subheader("📊 Parcours")
    dist = st.number_input("Distance (km)", value=25.0)
    dplus = st.number_input("Dénivelé Positif (m)", value=1200)
    tech = st.select_slider("Technicité du sol", options=[1.0, 1.1, 1.25], 
                           format_func=lambda x: "Facile" if x==1.0 else ("Moyen" if x==1.1 else "Technique"))

with col2:
    st.subheader("☁️ Météo")
    lat = st.number_input("Latitude de la course", value=45.92)
    lon = st.number_input("Longitude de la course", value=6.86)
    w_impact, temp, w_code = get_weather_impact(lat, lon)
    st.info(f"Conditions : {temp}°C | Impact : +{int((w_impact-1)*100)}% sur le temps")

# --- CALCULS FINAUX ---
# Base Naismith : 100m D+ = 1km plat
km_effort = dist + (dplus / 100)
temps_ideal = km_effort * avg_pace * tech
temps_meteo = temps_ideal * w_impact

def format_time(minutes):
    return f"{int(minutes // 60)}h {int(minutes % 60)}min"

st.divider()

# Affichage des résultats
c1, c2 = st.columns(2)
c1.metric("Temps estimé (Météo incluse)", format_time(temps_meteo))
c2.metric("Équivalent distance à plat", f"{km_effort:.1f} km")

# Graphique de comparaison
fig = go.Figure(data=[
    go.Bar(name='Théorique (Plat)', x=['Temps'], y=[dist * avg_pace], marker_color='#00CC96'),
    go.Bar(name='Avec Dénivelé', x=['Temps'], y=[temps_ideal - (dist * avg_pace)], marker_color='#636EFA'),
    go.Bar(name='Surcoût Météo', x=['Temps'], y=[temps_meteo - temps_ideal], marker_color='#EF553B')
])
fig.update_layout(barmode='stack', title="Décomposition de l'effort (en minutes)", height=400)
st.plotly_chart(fig, use_container_width=True)

st.caption("Outil basé sur la règle de Naismith ajustée et les données Open-Meteo.")
