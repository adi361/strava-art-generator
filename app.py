cat << 'EOF' > app.py
import streamlit as st
import folium
from streamlit_folium import st_folium
import gpxpy
import gpxpy.gpx
import requests
import math
import base64
from io import BytesIO
from PIL import Image

# Konfigurasi halaman antarmuka
st.set_page_config(page_title="Strava Art Generator", layout="wide")
st.title("Strava Art & Route Generator (Python Edition)")

# Inisialisasi session_state
if "start_point" not in st.session_state:
    st.session_state.start_point = [-0.5022, 117.1536]  # Default Samarinda

if "start_locked" not in st.session_state:
    st.session_state.start_locked = False

if "waypoints" not in st.session_state:
    st.session_state.waypoints = []

if "route_coords" not in st.session_state:
    st.session_state.route_coords = []

# Fungsi menghitung jarak total rute dalam Kilometer (Haversine Formula)
def calculate_total_distance(coords):
    if len(coords) < 2:
        return 0.0
    
    total_distance = 0.0
    R = 6371.0  # Radius bumi dalam kilometer
    
    for i in range(len(coords) - 1):
        lat1, lon1 = math.radians(coords[i][0]), math.radians(coords[i][1])
        lat2, lon2 = math.radians(coords[i+1][0]), math.radians(coords[i+1][1])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        total_distance += R * c
        
    return total_distance

# Fungsi untuk mengambil rute jalan nyata atau garis lurus
def update_route_geometry(start, waypoints, mode):
    full_points = [start] + waypoints
    if len(full_points) < 2:
        return full_points
        
    if mode == "Garis Lurus Bebas (Direct)":
        return full_points
    else:
        coords_str = ";".join([f"{p[1]},{p[0]}" for p in full_points])
        url = f"http://router.project-osrm.org/route/v1/foot/{coords_str}?overview=full&geometries=geojson"
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if "routes" in data and len(data["routes"]) > 0:
                    geometry = data["routes"][0]["geometry"]["coordinates"]
                    return [[coord[1], coord[0]] for coord in geometry]
        except Exception:
            pass
        return full_points

# Panel Kontrol di Kolom Kanan
col_map, col_ctrl = st.columns([3, 1])

with col_ctrl:
    st.subheader("Panel Kontrol Rute")

    # Fitur Unggah Gambar Cetak Biru / Template Seni
    st.write("🖼️ **Cetak Biru Seni (Gambar Template)**")
    uploaded_file = st.file_uploader("Upload pola (T-Rex, hewan, dll):", type=["png", "jpg", "jpeg"])
    
    overlay_data_url = None
    target_span_km = 5.0
    overlay_opacity = 0.5

    if uploaded_file is not None:
        img = Image.open(uploaded_file)
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode()
        overlay_data_url = f"data:image/png;base64,{img_b64}"
        
        target_span_km = st.slider("Ukuran Bentangan Gambar (KM)", min_value=1.0, max_value=15.0, value=5.0, step=0.5)
        overlay_opacity = st.slider("Transparansi Gambar", min_value=0.1, max_value=1.0, value=0.5, step=0.1)

    st.markdown("---")
    
    route_mode = st.radio(
        "Pilih Mode Jalur:",
        ["Garis Lurus Bebas (Direct)", "Mengikuti Jalan (Routing)"],
        index=0
    )

    if not st.session_state.start_locked:
        st.info("📍 **Fase 1:** Geser Titik Start dengan klik peta. Jika sudah pas, klik **Kunci Titik Start**.")
    else:
        st.success("🔒 **Fase 2:** Titik Start terkunci. Klik peta untuk membuat checkpoint.")

    if not st.session_state.start_locked:
        if st.button("🔒 Kunci Titik Start & Mulai Rute"):
            st.session_state.start_locked = True
            st.session_state.route_coords = update_route_geometry(st.session_state.start_point, st.session_state.waypoints, route_mode)
            st.rerun()
    else:
        if st.button("🔓 Ubah / Geser Ulang Titik Start"):
            st.session_state.start_locked = False
            st.session_state.waypoints = []
            st.session_state.route_coords = []
            st.rerun()

    st.markdown("---")

    if st.button("🗑️ Reset Seluruh Rute"):
        st.session_state.waypoints = []
        st.session_state.route_coords = []
        st.session_state.start_locked = False
        st.rerun()

    st.markdown("---")

    if len(st.session_state.route_coords) > 1:
        total_km = calculate_total_distance(st.session_state.route_coords)
        st.metric(label="📏 **Total Panjang Rute**", value=f"{total_km:.2f} km")

    st.markdown("---")

    # Manajemen Checkpoint Rute
    if len(st.session_state.waypoints) > 0:
        st.write("📍 **Daftar Checkpoint Alur Rute:**")
        points_to_remove = []
        for i, wp in enumerate(st.session_state.waypoints):
            col_info, col_del = st.columns([3, 1])
            with col_info:
                st.text(f"#{i+1}: {wp[0]:.4f}, {wp[1]:.4f}")
            with col_del:
                if st.button("❌", key=f"del_{i}"):
                    points_to_remove.append(i)
        
        if points_to_remove:
            for index in sorted(points_to_remove, reverse=True):
                st.session_state.waypoints.pop(index)
            st.session_state.route_coords = update_route_geometry(st.session_state.start_point, st.session_state.waypoints, route_mode)
            st.rerun()
    else:
        st.caption("Belum ada checkpoint rute.")

    st.markdown("---")

    def generate_gpx(route_coords):
        gpx = gpxpy.gpx.GPX()
        gpx_track = gpxpy.gpx.GPXTrack()
        gpx.tracks.append(gpx_track)
        gpx_segment = gpxpy.gpx.GPXTrackSegment()
        gpx_track.segments.append(gpx_segment)
        for coord in route_coords:
            gpx_segment.points.append(gpxpy.gpx.GPXTrackPoint(coord[0], coord[1]))
        return gpx.to_xml()

    if len(st.session_state.route_coords) > 1:
        gpx_data = generate_gpx(st.session_state.route_coords)
        st.download_button(
            label="📥 Download File GPX",
            data=gpx_data,
            file_name="strava_art_route.gpx",
            mime="application/gpx+xml"
        )
    else:
        st.warning("Buat minimal 1 checkpoint untuk mengaktifkan GPX.")

with col_map:
    m = folium.Map(location=st.session_state.start_point, zoom_start=14)

    if overlay_data_url:
        delta_lat = (target_span_km / 111.0) / 2.0
        delta_lon = (target_span_km / (111.0 * math.cos(math.radians(st.session_state.start_point[0])))) / 2.0
        center_lat = st.session_state.start_point[0]
        center_lon = st.session_state.start_point[1]
        bounds = [
            [center_lat - delta_lat, center_lon - delta_lon],
            [center_lat + delta_lat, center_lon + delta_lon]
        ]
        folium.raster_layers.ImageOverlay(
            image=overlay_data_url,
            bounds=bounds,
            opacity=overlay_opacity,
            interactive=False,
            cross_origin=False
        ).add_to(m)

    start_color = "green" if st.session_state.start_locked else "orange"
    start_popup = "Titik Mulai (Terkunci)" if st.session_state.start_locked else "Titik Mulai (Geser dengan klik peta)"

    folium.Marker(
        location=st.session_state.start_point,
        popup=start_popup,
        icon=folium.Icon(color=start_color, icon="play", prefix="fa")
    ).add_to(m)

    for i, wp in enumerate(st.session_state.waypoints):
        folium.CircleMarker(
            location=wp,
            radius=5,
            color="blue",
            fill=True,
            fill_color="blue",
            popup=f"Checkpoint {i+1}"
        ).add_to(m)

    if st.session_state.start_locked and len(st.session_state.waypoints) > 0:
        st.session_state.route_coords = update_route_geometry(st.session_state.start_point, st.session_state.waypoints, route_mode)

    if len(st.session_state.route_coords) > 1:
        folium.PolyLine(st.session_state.route_coords, color="red", weight=4, opacity=0.8).add_to(m)

    output = st_folium(m, width=700, height=580)

    if output and output.get("last_clicked"):
        clicked_lat = output["last_clicked"]["lat"]
        clicked_lon = output["last_clicked"]["lng"]
        new_point = [clicked_lat, clicked_lon]

        if not st.session_state.start_locked:
            st.session_state.start_point = new_point
            st.rerun()
        else:
            if not st.session_state.waypoints or st.session_state.waypoints[-1] != new_point:
                st.session_state.waypoints.append(new_point)
                st.session_state.route_coords = update_route_geometry(st.session_state.start_point, st.session_state.waypoints, route_mode)
                st.rerun()
