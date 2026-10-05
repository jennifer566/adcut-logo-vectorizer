"""Streamlit interface for the Adcut Logo Vectorizer development build."""

from io import BytesIO

import streamlit as st
from PIL import Image, UnidentifiedImageError

from adcut.export import export_dxf, export_svg
from adcut.pipeline import VectorizationError, VectorizationOptions, vectorize_image

st.set_page_config(page_title="Adcut Logo Vectorizer", page_icon="✂", layout="wide")
st.title("Adcut Logo Vectorizer")
st.caption(
    "Development build for reviewing image-to-CAD geometry. Do not send unvalidated output to cutting equipment."
)

with st.sidebar:
    st.header("Output settings")
    output_width = st.number_input("Output width", min_value=0.01, value=10.0, step=0.5)
    units = st.segmented_control("Units", options=["in", "mm"], default="in")
    color_count = st.slider("Maximum colors", min_value=2, max_value=12, value=4)
    simplification = st.slider(
        "Polyline simplification",
        min_value=0.0,
        max_value=0.02,
        value=0.002,
        step=0.001,
        format="%.3f",
    )
    ignore_border = st.checkbox("Ignore the dominant border color", value=True)

uploaded = st.file_uploader(
    "Choose artwork",
    type=["jpg", "jpeg", "png", "webp", "gif", "pdf"],
    help="PDF and GIF currently use the first page or frame.",
)

if uploaded is None:
    st.info("Upload artwork or use a file from the examples folder to begin.")
    st.stop()

data = uploaded.getvalue()
left, right = st.columns(2)
with left:
    st.subheader("Source")
    try:
        if not uploaded.name.lower().endswith(".pdf"):
            st.image(Image.open(BytesIO(data)), use_container_width=True)
        else:
            st.write("PDF selected. The first page will be rasterized during conversion.")
    except (OSError, UnidentifiedImageError):
        st.write("Preview unavailable. Conversion will report whether the file can be decoded.")

try:
    result = vectorize_image(
        data,
        filename=uploaded.name,
        options=VectorizationOptions(
            output_width=float(output_width),
            units=units or "in",
            color_count=color_count,
            simplification=simplification,
            ignore_border_color=ignore_border,
        ),
    )
except VectorizationError as exc:
    st.error(str(exc))
    st.stop()

with right:
    st.subheader("Traced boundaries")
    st.image(result.preview_png, use_container_width=True)

metric_columns = st.columns(4)
metric_columns[0].metric("Color regions", len(result.regions))
metric_columns[1].metric("Closed paths", result.path_count)
metric_columns[2].metric("Output width", f"{result.output_width:.3g} {result.units}")
metric_columns[3].metric("Output height", f"{result.output_height:.3g} {result.units}")

for warning in result.warnings:
    st.warning(warning)

dxf = export_dxf(result)
svg = export_svg(result)
download_columns = st.columns(2)
download_columns[0].download_button(
    "Download DXF",
    data=dxf,
    file_name="adcut-vectorized.dxf",
    mime="application/dxf",
    use_container_width=True,
)
download_columns[1].download_button(
    "Download SVG",
    data=svg,
    file_name="adcut-vectorized.svg",
    mime="image/svg+xml",
    use_container_width=True,
)
