# Adcut Logo Vectorizer

UNC COMP 523 Team E development repository.

## Current status

The repository contains a runnable image-to-CAD workflow. The Streamlit interface accepts JPEG, PNG, WEBP, GIF, and PDF files, traces color regions into SVG curves, applies an explicit physical width, previews the vector result, and exports SVG or DXF R2000.

VTracer now performs the raster-to-vector stage in spline mode. SVG cubic Bezier paths are preserved as native DXF `SPLINE` entities instead of being flattened into many short line segments. Pillow is used only to decode and normalize uploads; it does not trace the logo.

Native circle and circular-arc recognition, shared-edge deduplication, and manual path editing are not complete. AutoCAD, IGEMS, machine compatibility, and physical cutting tests are also still required. Do not send unvalidated output to cutting equipment.

## Platform

- Python 3.11 through 3.13
- Streamlit for the local browser interface
- VTracer for color segmentation and SVG spline tracing
- svgelements for structured SVG path parsing
- ezdxf for native DXF curves, layers, units, and serialization
- Pillow for upload decoding and pypdfium2 for first-page PDF rasterization
- uv for Python versions, dependency resolution, lockfile management, and commands
- pytest, Ruff, and pre-commit for verification

The application processes files locally. Installation requires internet access to obtain dependencies, but normal use does not require a hosted service.

## Setup with uv

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), clone the repository, and run these commands from the repository root:

```powershell
uv sync --locked --dev
uv run pytest
uv run pre-commit install
uv run pre-commit install --hook-type commit-msg
uv run streamlit run app.py
```

Open the address Streamlit prints, normally `http://localhost:8501`. The same `uv` commands work in PowerShell, Command Prompt, macOS Terminal, and Linux shells.

`uv.lock` is committed so teammates and CI resolve the same package versions. Change dependencies with `uv add <package>` or `uv remove <package>`, then commit both `pyproject.toml` and `uv.lock`.

## How vectorization works

1. **Decode the upload.** Pillow reads JPEG, PNG, WEBP, and the first GIF frame. pypdfium2 renders the first PDF page. Transparency is composited onto white and the image is normalized to RGBA.
2. **Trace to SVG curves.** The RGBA pixels are passed to VTracer in `spline` mode with `cutout` color hierarchy. VTracer clusters colors, removes small regions, fits curves, and returns SVG path data. OpenCV contours and Pillow polygon tracing are not used.
3. **Keep closed color regions.** The SVG XML is parsed structurally. Closed paths are grouped by fill color, and the dominant border color can be omitted as background.
4. **Preserve native geometry.** Cubic and quadratic SVG Bezier commands remain curves. The SVG download keeps the original path commands and adds physical dimensions.
5. **Create CAD output.** SVG paths are parsed with svgelements, scaled to the requested inches or millimeters, flipped into CAD coordinates, and passed to ezdxf. Curved sections become native DXF `SPLINE` entities; straight sections remain polylines. Each detected color receives its own named layer.
6. **Validate before fabrication.** The app reports region and curve counts, but exported files still require visual, scale, layer, and downstream software checks before cutting.

The curve simplification control is measured in source-image pixels. Larger values create fewer control points but can remove detail. The maximum-colors control limits VTracer's color clustering.

## Tests and compatibility

Run all checks locally with:

```powershell
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

GitHub Actions runs the locked project on Windows, Linux, and macOS with Python 3.11, 3.12, and 3.13. The matrix catches operating-system and Python-version differences before changes are merged.

The original sample images in `examples/` are safe to publish and can be regenerated with `uv run python scripts/create_samples.py`. They include adjacent regions, holes, and curves that expose known geometry limitations.

## Collaboration and tracking

Use short-lived `feature/` branches and pull requests into `main`. Review changes with another teammate and use conventional commit messages. Work is tracked on the [Adcut Logo Vectorizer Development Kanban board](https://github.com/users/jennifer566/projects/3). Do not commit customer artwork without permission; `samples/private/` is ignored.

## Next validation tasks

1. Obtain representative source files and accepted CAD output with permission to use them.
2. Confirm DXF version, units, scale, layers, curve conventions, and target AutoCAD/IGEMS versions.
3. Validate the SVG-first workflow against permitted client samples.
4. Recognize exact circles and circular arcs where tolerance allows.
5. Preserve holes and remove duplicate shared cut edges.
6. Add review and correction controls after observing the client's workflow.
7. Test scale, native entity counts, imports, and cuts in the downstream toolchain.

Success requires an image-to-DXF workflow accepted by Adcut, not just a syntactically valid file.

Project website: https://jennifer566.github.io/adcut-logo-vectorizer-site/

## References

- https://docs.astral.sh/uv/
- https://github.com/visioncortex/vtracer
- https://github.com/meerk40t/svgelements
- https://ezdxf.readthedocs.io/en/stable/path.html
- https://docs.streamlit.io/
- https://pypdfium2.readthedocs.io/en/stable/
- https://identity.unc.edu/resources/downloads/

The application uses these projects through their published packages and APIs. No source code has been copied from another vectorizer.
