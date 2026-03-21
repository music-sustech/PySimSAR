# Research: Version 0.1 Release Documentation

**Branch**: `003-release-docs` | **Date**: 2026-03-21

## R1: MkDocs Material Theme Configuration for LaTeX

**Decision**: Use `mkdocs-material` with `pymdownx.arithmatex` extension and MathJax 3 CDN.

**Rationale**: MkDocs Material is the most widely used MkDocs theme, provides built-in support for math via the `arithmatex` extension, and renders LaTeX through MathJax without a local TeX installation. MathJax 3 is significantly faster than MathJax 2 and supports all standard LaTeX math environments (aligned, cases, matrices, etc.).

**Alternatives considered**:
- **Sphinx + MyST**: More powerful cross-referencing and PDF output, but requires RST knowledge and heavier configuration. Overkill for a Markdown-first project.
- **Plain Markdown + KaTeX**: Faster rendering than MathJax but limited LaTeX environment support (no `aligned`, limited `cases`). Risky for complex SAR equations.
- **Jupyter Book**: Good for mixed code+math but adds substantial build complexity and dependencies.

**Configuration**:
```yaml
# mkdocs.yml
site_name: PySimSAR v0.1 Documentation
theme:
  name: material
  features:
    - navigation.sections
    - navigation.expand
    - navigation.top
    - content.code.copy
    - search.suggest
markdown_extensions:
  - pymdownx.arithmatex:
      generic: true
  - pymdownx.highlight:
      anchor_linenums: true
  - pymdownx.superfences:
      custom_fences:
        - name: mermaid
          class: mermaid
          format: !!python/name:pymdownx.superfences.fence_code_format
  - admonition
  - pymdownx.details
  - attr_list
  - toc:
      permalink: true
extra_javascript:
  - javascripts/mathjax.js
  - https://unpkg.com/mathjax@3/es5/tex-mml-chtml.js
extra_css: []
```

With `docs/javascripts/mathjax.js`:
```javascript
window.MathJax = {
  tex: {
    inlineMath: [["$", "$"], ["\\(", "\\)"]],
    displayMath: [["$$", "$$"], ["\\[", "\\]"]],
    processEscapes: true,
    processEnvironments: true,
  },
  options: {
    ignoreHtmlClass: ".*|",
    processHtmlClass: "arithmatex",
  },
};
```

## R2: Documentation Structure Best Practices for Scientific Software

**Decision**: Use a topic-based structure with math content in a dedicated subdirectory, following the Diataxis documentation framework (tutorials, how-to guides, reference, explanation).

**Rationale**: The Diataxis framework maps well to the spec's user stories:
- **Tutorial** → Getting Started (US1)
- **Reference** → Data Structures, API Reference (US2, US5)
- **Explanation** → Mathematical Principles, Architecture (US3)
- **How-to Guide** → Customization/Programming Guide (US4)

Separating math into `math/` keeps equation-heavy content from overwhelming navigation and allows researchers to browse the mathematical reference independently.

**Alternatives considered**:
- **Single monolithic document**: Easier to search with Ctrl+F but unwieldy at the expected 200+ pages equivalent. Poor navigation.
- **Per-module documentation**: Mirrors code structure exactly but creates fragmented reading experience for cross-cutting concerns (e.g., a simulation involves scene + radar + platform + engine).

## R3: SAR Literature References for Algorithm Documentation

**Decision**: Primary references for each algorithm family:

| Algorithm Domain | Primary Reference | Secondary Reference |
|-----------------|-------------------|---------------------|
| SAR Signal Model | Cumming & Wong (2005), *Digital Processing of SAR Data* | Soumekh (1999), *Synthetic Aperture Radar Signal Processing* |
| LFM Waveform | Richards (2014), *Fundamentals of Radar Signal Processing*, Ch. 4 | Skolnik (2008), *Radar Handbook*, Ch. 8 |
| FMCW Waveform | Stove (1992), "Linear FMCW radar techniques" | Meta et al. (2007), "Signal processing for FMCW SAR" |
| Range-Doppler Algorithm | Cumming & Wong (2005), Ch. 6 | Bamler (1992), "A comparison of range-Doppler and wavenumber domain SAR focusing algorithms" |
| Chirp Scaling Algorithm | Raney et al. (1994), "Precision SAR processing using chirp scaling" | Cumming & Wong (2005), Ch. 7 |
| Omega-K Algorithm | Stolt (1978), migration principle; Cafforio et al. (1991) | Cumming & Wong (2005), Ch. 9 |
| Motion Compensation | Moreira & Huang (1994), "Airborne SAR processing of highly squinted data" | Fornaro (1999), "Trajectory deviations in airborne SAR" |
| PGA Autofocus | Wahl et al. (1994), "Phase gradient autofocus" | Jakowatz et al. (1996), *Spotlight-Mode SAR: A Signal Processing Approach* |
| Map Drift Autofocus | Bamler & Eineder (1996) | — |
| Minimum Entropy Autofocus | Morrison et al. (2002); Kragh (2006), "Minimum-entropy autofocus for spotlight SAR" | — |
| PPP Autofocus | Eichel et al. (1989), "Phase gradient algorithm for autofocus" | — |
| Slant-to-Ground | Cumming & Wong (2005), Ch. 12 | — |
| Georeferencing | Schreier (1993), *SAR Geocoding* | — |
| Pauli Decomposition | Lee & Pottier (2009), *Polarimetric Radar Imaging* | Cloude (2009), *Polarisation* |
| Freeman-Durden | Freeman & Durden (1998), "Three-component scattering model" | — |
| Yamaguchi | Yamaguchi et al. (2005), "Four-component scattering model" | — |
| Cloude-Pottier | Cloude & Pottier (1997), "Entropy-based classification scheme" | — |

**Rationale**: These are the canonical references most widely cited in the SAR community. Using them ensures the documentation is credible and traceable.

## R4: Diagram Approach

**Decision**: Use Mermaid for architecture/flow diagrams (renders natively in MkDocs Material and GitHub) and pre-rendered PNG for SAR geometry diagrams that require precise spatial layouts.

**Rationale**: Mermaid diagrams are version-controllable as text, render in both GitHub and MkDocs, and are easy to update. However, SAR imaging geometry (antenna, beam, ground swath) requires precise spatial rendering that text-based diagram tools cannot achieve — these are better as carefully crafted PNGs.

**Alternatives considered**:
- **All Mermaid**: Cannot handle spatial geometry diagrams well.
- **All PNG**: Harder to update, binary files in git, but highest visual quality.
- **PlantUML**: Requires a Java dependency for rendering; Mermaid is natively supported.

## R5: Code Example Validation Strategy

**Decision**: All runnable code examples will be tested by executing them against shipped presets before documentation is finalized. Examples will import from `pySimSAR` and use the default_stripmap preset.

**Rationale**: The spec requires at least 5 runnable examples (SC-006). These must be validated to prevent documentation rot. Testing against shipped presets ensures examples work without external data.

**Approach**: Each code example will be a self-contained script that can be run as `python example_name.py`. Examples will be embedded in documentation as fenced code blocks and also saved as standalone `.py` files in `docs/examples/` for easy testing.
