# Adcut Logo Vectorizer

UNC COMP 523 Team E. Development build established October 4, 2026.

## Current status

This repository contains a runnable first image-to-CAD workflow. The Streamlit interface accepts JPEG, PNG, WEBP, GIF, and PDF files, reduces colors, traces closed foreground regions, applies an explicit physical width, previews detected boundaries, and exports SVG or DXF. The earlier native-circle exporter and its tests remain available.

The current image tracer exports closed polylines. Native circle/arc fitting and shared-edge deduplication are not implemented yet, so every conversion displays warnings. No AutoCAD, IGEMS, machine compatibility, or cutting tests have been completed. Do not send unvalidated output to cutting equipment.

## Selected starting platform

- Python 3.11, VS Code, Git/GitHub.
- Streamlit for a local browser interface on Windows.
- Pillow for image decoding; OpenCV and NumPy for color segmentation and contours.
- ezdxf for DXF entities and serialization.
- pypdfium2 for later PDF raster import. Preserve vector PDF geometry where feasible after sample review.
- pytest and Ruff for tests and formatting; pre-commit for local checks.

Local processing is the initial deployment choice to keep installation and data flow simple. The client permits cloud deployment, which remains a future option. A local Streamlit app needs a running Python process but does not require a hosted service. Installation may need internet access. PyInstaller packaging is deferred until the basic workflow is validated.

React/Vue would offer more editing control but add a separate frontend and API. Potrace/vtracer remain comparison candidates; raster tracing alone does not solve the native arc requirement. Native DWG export is not included. Validate a licensing-compatible approach before adding an external converter. Review dependencies and notices before distribution.

## Windows setup

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python -m pytest
.venv\Scripts\pre-commit install
.venv\Scripts\pre-commit install --hook-type commit-msg
```

The dependencies are bounded development ranges, not a reproducible release lock. Pin a tested environment before distribution.

Run the application from the repository root:

```powershell
.venv\Scripts\streamlit run app.py
```

Then open the local address Streamlit prints, normally `http://localhost:8501`.

The original sample images in `examples/` are safe to publish and can be regenerated with `python scripts/create_samples.py`. The examples intentionally include adjacent regions and holes that expose known geometry limitations.

## Collaboration

Use short-lived `feature/` branches and pull requests into `main`. Review changes with another teammate. Use conventional commits. CI runs tests and Ruff on Windows. Do not commit customer artwork without permission; `samples/private/` is ignored. Repository access must be granted to the actual teammate accounts.

## Next implementation tasks

1. Obtain representative source files and accepted CAD output with permission to use them.
2. Confirm DXF version, units, scale, layers, arc conventions, and target AutoCAD/IGEMS versions.
3. Validate the current upload, color reduction, tracing, preview, SVG, and DXF workflow against permitted client samples.
4. Fit circles/arcs with an agreed tolerance; preserve holes and avoid duplicate cut paths.
5. Decide how users should control color reduction after testing real artwork.
6. Test scale, native entity counts, and import into the actual downstream tools.
7. Evaluate PDF region selection and DWG only after confirming priority and feasibility.

Success requires an image-to-DXF workflow accepted by Adcut, not just a syntactically valid file. Do not run unvalidated output on cutting equipment.

Project website: https://jennifer566.github.io/adcut-logo-vectorizer-site/

## References

- https://docs.streamlit.io/get-started/installation
- https://docs.opencv.org/4.x/d4/d73/tutorial_py_contours_begin.html
- https://ezdxf.readthedocs.io/en/stable/
- https://pypdfium2.readthedocs.io/en/stable/
- https://identity.unc.edu/resources/downloads/ (optional approved university-brand test source; usage restrictions apply)

The application uses these projects through their published packages and APIs. No source code has been copied from another vectorizer. Potrace and vtracer remain evaluation candidates for later comparison against the project's CAD-geometry requirements.
