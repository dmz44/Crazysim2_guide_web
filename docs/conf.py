# Sphinx configuration for the CrazySim2 Simulation Guide.
# Build locally:  pip install -r docs/requirements.txt && sphinx-build -b html docs docs/_build/html

import datetime

project = 'CrazySim2 Simulation Guide'
author = 'MinHyuk Park'
copyright = f'{datetime.date.today().year}, {author}'
release = '2.0'

# -- GitHub coordinates (used for "Edit on GitHub" links) --------------------
GITHUB_USER = 'dmz44'
GITHUB_REPO = 'Crazysim2_guide_web'
GITHUB_BRANCH = 'main'

extensions = [
    'myst_parser',          # write pages in Markdown
    'sphinx_copybutton',    # copy button on code blocks
    'sphinx.ext.githubpages',  # writes .nojekyll so GitHub Pages serves _static/
]

myst_enable_extensions = [
    'colon_fence',   # ::: fences for admonitions
    'deflist',
    'attrs_inline',
    'substitution',
    'tasklist',
]
myst_heading_anchors = 3

myst_substitutions = {
    'repo_url': f'https://github.com/{GITHUB_USER}/{GITHUB_REPO}',
}

source_suffix = {'.md': 'markdown', '.rst': 'restructuredtext'}
master_doc = 'index'
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store', 'README.md']

# Strip shell prompts when copying ("$ ", "(container) $ ")
copybutton_prompt_text = r'^(\(container\) )?\$ |^>>> '
copybutton_prompt_is_regexp = True

# -- HTML: Read the Docs theme -----------------------------------------------
html_theme = 'sphinx_rtd_theme'
html_title = 'CrazySim2 Simulation Guide'
html_static_path = ['_static']
html_css_files = ['custom.css']
html_logo = '_static/img/logo.svg'
html_favicon = '_static/img/logo.svg'
html_theme_options = {
    'navigation_depth': 3,
    'collapse_navigation': False,
    'sticky_navigation': True,
    'style_external_links': True,
    'prev_next_buttons_location': 'both',
}
html_context = {
    'display_github': True,
    'github_user': GITHUB_USER,
    'github_repo': GITHUB_REPO,
    'github_version': GITHUB_BRANCH,
    'conf_py_path': '/docs/',
}
html_show_sourcelink = False
