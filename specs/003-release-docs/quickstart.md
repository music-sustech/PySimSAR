# Quickstart: Version 0.1 Release Documentation

**Branch**: `003-release-docs` | **Date**: 2026-03-21

## Developer Setup

### Prerequisites

- Python 3.10+ (project uses 3.14)
- Git
- Text editor with Markdown preview (VS Code recommended for live LaTeX preview)

### Install Documentation Dependencies

```bash
pip install mkdocs-material
```

This installs MkDocs, Material theme, and all required extensions (pymdownx for LaTeX).

### Local Documentation Preview

```bash
# From repo root
mkdocs serve
```

Open `http://localhost:8000` — the site auto-reloads on file save.

### Build Static Site

```bash
mkdocs build
```

Output in `site/` directory (add `site/` to `.gitignore`).

### Deploy to GitHub Pages

```bash
mkdocs gh-deploy
```

## Writing Workflow

### Adding a New Chapter

1. Create a `.md` file in the appropriate `docs/` subdirectory
2. Add the file to the `nav:` section in `mkdocs.yml`
3. Preview with `mkdocs serve`

### Writing LaTeX Equations

Inline: `$f_c$` renders as $f_c$

Display:
```markdown
$$
s_{tx}(t) = \exp\left(j\pi K_r t^2\right)
$$
```

### Adding Diagrams

**Mermaid** (for flow/architecture diagrams):
````markdown
```mermaid
graph LR
    A[Scene + Radar] --> B[SimulationEngine]
    B --> C[RawData]
    C --> D[PipelineRunner]
    D --> E[SARImage]
```
````

**PNG** (for geometry diagrams): place in `docs/assets/` and reference:
```markdown
![SAR Geometry](assets/sar-geometry.png)
```

### Adding Code Examples

Fenced code blocks with language hint:
````markdown
```python
from pySimSAR.core.scene import Scene, PointTarget
scene = Scene()
scene.add_target(PointTarget(position=[0, 0, 0], rcs=1.0))
```
````

## File Checklist

The documentation is complete when all files in the `docs/` tree exist and pass their chapter contracts defined in `specs/003-release-docs/contracts/doc-outline.md`.

## Validation

1. All code examples must run successfully: `python docs/examples/<script>.py`
2. MkDocs builds without warnings: `mkdocs build --strict`
3. All internal links resolve (no broken cross-references)
4. LaTeX renders correctly in local preview
