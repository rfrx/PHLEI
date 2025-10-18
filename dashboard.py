import dash
from dash import html, dcc, Output, Input
import dash_leaflet as dl
import plotly.express as px
import pandas as pd
import numpy as np
from fastkml import kml
from shapely.geometry import LineString
import base64
import re

# --------------- Helper functions -----------------

import re
import os
import xml.etree.ElementTree as ET

def abgr_to_hex(abgr):
    """Convert KML ABGR (8 hex chars) -> #RRGGBB.
       Example: 'ff0000ff' -> '#ff0000' (red)
    """
    abgr = abgr.strip()
    # Accept either 6 or 8 hex chars; if 8, first two are alpha
    if len(abgr) == 8:
        a, b, g, r = abgr[0:2], abgr[2:4], abgr[4:6], abgr[6:8]
        return f"#{r}{g}{b}"
    elif len(abgr) == 6:
        # assume RRGGBB already
        return f"#{abgr}"
    else:
        return None

def parse_kml_colors(kml_path):
    """
    Parse tracks and their colors from a KML file.
    Returns list of dicts: {'name':..., 'coords': [(lat, lon), ...], 'color': '#rrggbb'}
    """
    ns = {
        'kml': 'http://www.opengis.net/kml/2.2',
        'gx': 'http://www.google.com/kml/ext/2.2'
    }

    tree = ET.parse(kml_path)
    root = tree.getroot()

    # Build style map: id -> color (from LineStyle/color)
    style_map = {}
    # Styles can be direct children of Document (or root)
    for style in root.findall(".//kml:Style", ns):
        sid = style.attrib.get('id')
        if not sid:
            continue
        # find LineStyle/color under this Style
        color_el = style.find(".//kml:LineStyle/kml:color", ns)
        if color_el is not None and color_el.text:
            hexc = abgr_to_hex(color_el.text.strip())
            if hexc:
                style_map[f"#{sid}"] = hexc  # styleUrl uses '#id'
        # also allow StyleMap -> pair -> styleUrl (if KML uses StyleMap)
    # Also process StyleMap entries that reference styles (optional)
    # (left out for brevity, but can be added if needed)

    tracks = []
    # Iterate over all Placemark elements that contain LineString
    for pm in root.findall(".//kml:Placemark", ns):
        name_el = pm.find("kml:name", ns)
        name = name_el.text.strip() if name_el is not None and name_el.text else None

        # styleUrl may be like '#4' or an absolute URL
        style_url_el = pm.find("kml:styleUrl", ns)
        style_url = style_url_el.text.strip() if style_url_el is not None and style_url_el.text else None

        ls = pm.find(".//kml:LineString", ns)
        if ls is None:
            continue

        coords_el = ls.find("kml:coordinates", ns)
        if coords_el is None or not coords_el.text:
            continue

        coords_text = coords_el.text.strip()
        # coordinates are whitespace-separated tuples: lon,lat[,alt]
        coords = []
        for part in re.split(r'\s+', coords_text.strip()):
            if not part:
                continue
            comps = part.split(',')
            if len(comps) < 2:
                continue
            try:
                lon = float(comps[0])
                lat = float(comps[1])
            except ValueError:
                continue
            # Leaflet/dash-leaflet expects [lat, lon]
            coords.append((lat, lon))

        # Determine color: placemark style -> style_map -> fallback
        color = None
        if style_url and style_url in style_map:
            color = style_map[style_url]
        else:
            # try inline LineStyle inside Placemark (rare)
            inline_color_el = pm.find(".//kml:LineStyle/kml:color", ns)
            if inline_color_el is not None and inline_color_el.text:
                color = abgr_to_hex(inline_color_el.text.strip())

        if color is None:
            color = "#0000ff"  # fallback

        tracks.append({
            'name': name,
            'coords': coords,
            'color': color
        })

    return tracks

# --------------- Build Dash app -----------------

app = dash.Dash(__name__)

# Load and process KML file
tracks = []
kml_dir = "data"
for fname in os.listdir(kml_dir):
    if fname.lower().endswith(".kml"):
        tracks.extend(parse_kml_colors(os.path.join(kml_dir, fname)))

# Compute percental values from sum
# Hardcoded for the Bar Plot, calculation from the other script.
counts = [1781, 136, 98, 72, 134]
total = sum(counts)
percental = [round(c / total * 100, 2) for c in counts]

# Create bar plot
bar_fig = px.bar(
    x=[str(i+1) for i in range(5)],
    y=percental,
    labels={"x": "Qualität", "y": "% der Segmente"},
    title="Radstreckenqualitätsverteilung",
)

# Create leaflet layers
track_layers = [
    dl.Polyline(positions=t['coords'], color=t['color'], weight=4)
    for t in tracks
]

# Layout
app.layout = html.Div(
    style={
        'height': '100%',
        'width': '100%',
        'backgroundColor': '#f2f2f3',
        'paddingBottom': '40px',
    },
    children=[
        html.Div(
            style={
                'backgroundColor': '#fd4cc4ff',
                'padding': '20px 0',
                'width': '100%',
                'textAlign': 'center',
                'boxShadow': '0 2px 8px rgba(0,0,0,0.08)',
                'fontFamily': 'Arial, sans-serif',
            },
            children=[
                html.H1("PHLEI", style={'color': 'white', 'marginBottom': '0'}),
                html.H2(
                    "Potsdam Holperfrei - Locker Erfahrbare Infrastruktur",
                    style={'color': 'white', 'fontWeight': 'normal', 'marginTop': '5px'}
                )
            ]
        ),
        dl.Map(
            center=[52.3970309, 13.0593217],
            zoom=14,
            children=[
                dl.TileLayer(),
                dl.LayerGroup(track_layers)
            ],
            style={'height': '500px', 'width': '60%', 'margin': "40px auto 0 auto"}
        ),
        dcc.Graph(figure=bar_fig, style={'height': '400px', 'width': '60%', 'padding': '20px', 'margin': 'auto', 'backgroundColor': '#f2f2f3'})
    ]
)

# --------------- Run -----------------
if __name__ == "__main__":
    app.run(debug=False)
