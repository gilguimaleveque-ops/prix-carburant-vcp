import streamlit as st
import requests
import zipfile
import io
import pandas as pd
import re
from lxml import etree
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import folium
from streamlit_folium import st_folium

# v4.1.0 - LG-PRESSE | UI/UX Premium & Code Optimisé

st.set_page_config(
    page_title="LG-PRESSE | Carburant VCP", 
    page_icon="⛽", 
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- MOTEUR DE DÉTECTION D'ENSEIGNE ---
def get_brand_info(adresse: str, ville: str) -> Dict[str, str]:
    brands = {
        "LECLERC": {"name": "E.Leclerc", "color": "#0052a5", "accent": "#ffdd00"},
        "TOTAL": {"name": "TotalEnergies", "color": "#ff0000", "accent": "#002a8f"},
        "INTERMARCHE": {"name": "Intermarché", "color": "#e2001a", "accent": "#000000"},
        "SUPER U": {"name": "Système U", "color": "#003da5", "accent": "#ffffff"},
        "HYPER U": {"name": "Système U", "color": "#003da5", "accent": "#ffffff"},
        "ESSO": {"name": "Esso", "color": "#ed1c24", "accent": "#ffffff"},
        "CARREFOUR": {"name": "Carrefour", "color": "#00387b", "accent": "#ed1c24"},
        "AUCHAN": {"name": "Auchan", "color": "#e1001a", "accent": "#ffffff"},
        "AVIA": {"name": "Avia", "color": "#e30613", "accent": "#ffffff"},
        "CASINO": {"name": "Casino", "color": "#008a42", "accent": "#ffffff"},
        "BP": {"name": "BP", "color": "#00aa3f", "accent": "#ffffff"},
        "SHELL": {"name": "Shell", "color": "#fbce07", "accent": "#e3001b"}
    }
    
    search_string = f"{adresse} {ville}".upper()
    # Nettoyage pour éviter les faux positifs (Boîte Postale)
    search_string = re.sub(r"\bBP\s*\d+", "", search_string)
    
    for key, info in brands.items():
        if key in search_string:
            return info
    return {"name": "Station Indépendante", "color": "#475569", "accent": "#f8fafc"}

# --- STYLE CSS MODERNISÉ ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    
    .main { background-color: #f8fafc; }
    
    /* Carte Station Premium */
    .station-card { 
        padding: 32px; 
        border-radius: 20px; 
        background: #ffffff; 
        margin: 20px 0;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        border: 1px solid #f1f5f9;
        transition: transform 0.2s ease;
    }
    
    .brand-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 20px;
    }
    
    .brand-badge { 
        padding: 6px 14px; 
        border-radius: 8px; 
        color: white; 
        font-weight: 700; 
        font-size: 0.9rem; 
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .status-badge { 
        padding: 4px 10px; 
        border-radius: 6px; 
        font-weight: 600; 
        font-size: 0.75rem; 
        color: white; 
    }
    
    .price-container {
        display: flex;
        align-items: baseline;
        gap: 8px;
        margin: 10px 0;
    }
    
    .price-text { 
        font-size: 4rem !important; 
        font-weight: 800; 
        margin: 0; 
        line-height: 0.9;
        letter-spacing: -2px;
    }
    
    .currency { font-size: 1.5rem; font-weight: 600; color: #64748b; }

    .address-text { 
        color: #1e293b !important; 
        font-size: 1.1rem !important; 
        font-weight: 600; 
        margin: 15px 0 5px 0; 
    }
    
    .city-text { color: #64748b; font-size: 0.9rem; margin-bottom: 15px; }
    
    .service-badge { 
        background: #f1f5f9; 
        color: #475569; 
        padding: 4px 10px; 
        border-radius: 6px; 
        font-size: 0.75rem; 
        margin-right: 6px; 
        margin-bottom: 6px; 
        display: inline-block;
        font-weight: 500;
    }
    
    .footer-info { 
        color: #94a3b8; 
        font-size: 0.75rem; 
        margin-top: 20px; 
        padding-top: 15px;
        border-top: 1px solid #f1f5f9;
        display: flex;
        justify-content: space-between;
    }
    </style>
    """, unsafe_allow_html=True)

# --- CACHE DES DONNÉES ---
@st.cache_resource(ttl=600)
def fetch_fuel_data():
    url = "https://donnees.roulez-eco.fr/opendata/instantane"
    try:
        r = requests.get(url, timeout=15)
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            xml_file = z.namelist()[0]
            with z.open(xml_file) as f:
                return etree.fromstring(f.read())
    except Exception as e:
        st.error(f"Erreur de connexion : {e}")
        return None

@st.cache_data(ttl=3600)
def get_locations_list(_root):
    if _root is None: return []
    return sorted(list(set([f"{s.get('cp')} - {s.find('ville').text.upper()}" for s in _root.xpath("//pdv") if s.find('ville') is not None])))

@st.cache_data(ttl=86400)
def get_annual_data_raw():
    url = "https://donnees.roulez-eco.fr/opendata/annee"
    try:
        r = requests.get(url, timeout=60)
        return r.content
    except: return None

def get_history_data(pdv_id: str, fuel_name: str) -> pd.DataFrame:
    content = get_annual_data_raw()
    if not content: return pd.DataFrame()
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            with z.open(z.namelist()[0]) as f:
                context = etree.iterparse(f, events=('end',), tag='pdv')
                data = []
                for _, elem in context:
                    if elem.get('id') == pdv_id:
                        for price in elem.xpath(f"prix[@nom='{fuel_name}']"):
                            val = price.get("valeur")
                            maj = price.get("maj")
                            if val and maj:
                                data.append({"Date": pd.to_datetime(maj), "Prix": float(val)})
                        elem.clear()
                        break
                    elem.clear()
                if data: return pd.DataFrame(data).set_index("Date").sort_index()
    except: pass
    return pd.DataFrame()

# --- UI PRINCIPALE ---
st.write("") # Spacer
c_logo_1, c_logo_2, c_logo_3 = st.columns([1, 1, 1])
with c_logo_2:
    st.image("https://www.lg-presse.fr/gallery/logo%20LG%20Presse.jpg?ts=1771514472", width=100)

st.markdown("<h1 style='text-align: center; color: #1e293b; margin-bottom: 0;'>Opti-Carburant</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #64748b; font-size: 1.1rem;'>Trouvez le meilleur prix en un clic.</p>", unsafe_allow_html=True)

with st.expander("ℹ️ Informations Légales & Guide"):
    st.markdown("""
    Le site **prix-carburants.gouv.fr** est le seul site officiel de l’Etat recensant les prix en France. 
    L'arrêté du 12/12/2006 rend obligatoire la déclaration pour les débits > 500m³/an.
    
    [Accéder au site officiel](https://www.prix-carburants.gouv.fr)
    """)

root = fetch_fuel_data()

if root is not None:
    locations = get_locations_list(root)

    # Zone de filtrage épurée
    with st.container():
        row1_1, row1_2 = st.columns([2, 1])
        with row1_1:
            selected_loc = st.selectbox("📍 Où cherchez-vous ?", options=[""] + locations, help="Saisissez une ville ou un code postal")
        with row1_2:
            fuel_choice = st.selectbox("⛽ Carburant", ["Gazole", "SP95-E10", "SP98", "SP95", "E85", "GPLc"])
        
        row2_1, row2_2 = st.columns([2, 1])
        with row2_1: 
            filter_24h = st.toggle("🕒 Uniquement Automate 24/24", value=False)
        with row2_2: 
            tank_vol = st.number_input("🚗 Volume du plein (L)", 1, 200, 50)

    if selected_loc:
        target_cp = selected_loc.split(" - ")[0]
        results = []

        for station in root.xpath(f"//pdv[@cp='{target_cp}']"):
            ville_xml = (station.find("ville").text or "").upper()
            services = [s.text for s in station.xpath(".//service")]
            
            if filter_24h and "Automate CB 24/24" not in services:
                continue
            
            # Horaires
            schedule = []
            for jour in station.xpath("horaires/jour"):
                nom, ferme = jour.get("nom"), jour.get("ferme")
                plages = [f"{h.get('ouverture')}-{h.get('fermeture')}" for h in jour.xpath("horaire")]
                schedule.append(f"{nom} : {'Fermé' if ferme == '1' or not plages else ', '.join(plages)}")

            for prix in station.xpath(f"prix[@nom='{fuel_choice}']"):
                maj_dt = datetime.fromisoformat(prix.get("maj"))
                results.append({
                    "id": station.get("id"),
                    "cp": target_cp, 
                    "adresse": (station.find("adresse").text or "").upper(),
                    "ville": ville_xml, 
                    "prix": float(prix.get("valeur")),
                    "maj": maj_dt.strftime("%d/%m/%Y %H:%M"), 
                    "is_old": datetime.now() - maj_dt.replace(tzinfo=None) > timedelta(hours=48),
                    "lat": float(station.get("latitude")) / 100000,
                    "lon": float(station.get("longitude")) / 100000,
                    "services": services,
                    "schedule": schedule
                })

        if results:
            # Tri par prix croissant
            results_sorted = sorted(results, key=lambda x: x['prix'])
            best = results_sorted[0]
            
            brand = get_brand_info(best['adresse'], best['ville'])
            status_color = "#f59e0b" if best['is_old'] else "#10b981"
            status_text = "MAJ INCERTAINE" if best['is_old'] else "PRIX RÉCENT"
            cout_plein = best['prix'] * tank_vol
            
            # Affichage de la meilleure station
            st.markdown(f"""
                <div class="station-card">
                    <div class="brand-header">
                        <div class="brand-badge" style="background-color: {brand['color']};">{brand['name']}</div>
                        <span class="status-badge" style="background-color: {status_color};">{status_text}</span>
                    </div>
                    <div class="price-container">
                        <h1 class="price-text" style="color: {brand['color']};">{best['prix']:.3f}</h1>
                        <span class="currency">€/L</span>
                    </div>
                    <div style="font-weight: 600; font-size: 1rem; color: #475569; margin-bottom: 10px;">
                        💰 Total pour {tank_vol}L : <span style="color: #0f172a;">{cout_plein:.2f} €</span>
                    </div>
                    <p class="address-text">{best['adresse']}</p>
                    <p class="city-text">{best['cp']} {best['ville']}</p>
                    <div style="margin-top:15px;">
                        {"".join([f'<span class="service-badge">{s}</span>' for s in best['services'][:6]])}
                    </div>
                    <div class="footer-info">
                        <span>ID: {best['id']}</span>
                        <span>Mise à jour : {best['maj']}</span>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            # Actions secondaires
            c_btn1, c_btn2, c_btn3 = st.columns(3)
            with c_btn1:
                st.link_button("📍 Itinéraire", f"https://www.google.com/maps/search/?api=1&query={best['lat']},{best['lon']}", use_container_width=True)
            with c_btn2:
                st.link_button("📷 Vue Rue", f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={best['lat']},{best['lon']}", use_container_width=True)
            with c_btn3:
                show_history = st.button("📈 Historique", use_container_width=True)

            if show_history:
                with st.spinner("Analyse des tendances..."):
                    df_hist = get_history_data(best['id'], fuel_choice)
                    if not df_hist.empty:
                        st.line_chart(df_hist, y="Prix", color="#0052a5")
                    else:
                        st.warning("Aucun historique disponible pour cette station.")

            # Autres stations
            with st.expander("📊 Comparer avec les autres stations de la zone"):
                for s in results_sorted[1:]: # On saute la première car déjà affichée
                    b_info = get_brand_info(s['adresse'], s['ville'])
                    st.markdown(f"""
                        <div style="padding: 12px 0; border-bottom: 1px solid #f1f5f9; display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <div style="font-weight:700; color: {b_info['color']}; font-size: 0.95rem;">{b_info['name']}</div>
                                <div style="font-size:0.8rem; color:#64748b;">{s['adresse'].title()}</div>
                            </div>
                            <div style="text-align:right;">
                                <div style="font-size:1.1rem; font-weight:800; color:#1e293b">{s['prix']:.3f} €</div>
                                <div style="font-size:0.7rem; color:#94a3b8;">+{s['prix']-best['prix']:.3f}€</div>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)

            # Carte
            st.write("")
            m = folium.Map(location=[best['lat'], best['lon']], zoom_start=15, control_scale=True)
            folium.TileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri', name='Satellite').add_to(m)
            
            # Ajout des autres stations sur la carte
            for s in results_sorted:
                is_best = s['id'] == best['id']
                folium.Marker(
                    [s['lat'], s['lon']], 
                    icon=folium.Icon(color='green' if is_best else 'blue', icon='info-sign'),
                    tooltip=f"{s['prix']:.3f} €"
                ).add_to(m)
            
            st_folium(m, width="100%", height=400, returned_objects=[])
            
        else:
            st.error("Désolé, aucune station n'a été trouvée pour ce carburant dans cette localité.")
    else:
        st.info("👋 Bienvenue ! Veuillez sélectionner une commune ci-dessus pour comparer les prix.")

# Footer simple
st.markdown("---")
st.markdown("<p style='text-align: center; color: #94a3b8; font-size: 0.8rem;'>v4.1.0 Premium | Design by LG Codage x LG-PRESSE</p>", unsafe_allow_html=True)