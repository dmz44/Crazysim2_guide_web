# Publishing and editing this site

This site is built with [Sphinx](https://www.sphinx-doc.org/) and the
[Read the Docs theme](https://sphinx-rtd-theme.readthedocs.io/). Pages are
Markdown files (via [MyST](https://myst-parser.readthedocs.io/)) in `docs/`.
A GitHub Actions workflow builds the site and publishes it to GitHub Pages on
every push to `main`.

## One-time GitHub setup

1. Push the repository (including `docs/` and `.github/workflows/docs.yml`)
   to GitHub.
2. On GitHub, open **Settings → Pages** and set **Source** to
   **GitHub Actions**.
3. Push to `main` (or run the workflow from the **Actions** tab). After a
   minute or two the site is live at
   `https://<user>.github.io/<repository>/` — for this repository
   ([dmz44/Crazysim2_guide_web](https://github.com/dmz44/Crazysim2_guide_web)),
   <https://dmz44.github.io/Crazysim2_guide_web/>.

Pull requests build the site too (without publishing), so broken links or
syntax errors show up as a failed check.

## Build it locally

```console
$ python3 -m venv .venv && source .venv/bin/activate
$ pip install -r docs/requirements.txt
$ sphinx-build -b html docs docs/_build/html
$ xdg-open docs/_build/html/index.html
```

For live reload while writing, `pip install sphinx-autobuild` and run
`sphinx-autobuild docs docs/_build/html`.

## Writing pages

- Add a new `.md` file under `docs/` and list it in a `toctree` in
  `docs/index.md`.
- Admonitions: ` :::{note} ... ::: `, ` :::{warning} ... ::: `, ` :::{tip} ... ::: `.
- Include code straight from the repository so the docs never drift from the
  scripts:

  ````md
  ```{literalinclude} ../../examples/fly_square.py
  :language: python
  :pyobject: preflight
  ```
  ````

- Images go in `docs/_static/img/`.
- Prefix shell commands with `$ ` (host) or `(container) $ `; the copy button
  strips the prompt.

## Hosting on Read the Docs instead

The same sources build on [readthedocs.org](https://readthedocs.org): import
the repository there and it will pick up `.readthedocs.yaml` at the repository
root.
