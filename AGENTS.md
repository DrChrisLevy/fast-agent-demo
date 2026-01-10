Use FastHTML. See these links https://fastht.ml/docs/llms.txt and visit appropriate docs.
Also be sure to use only DaisyUI so that themes works. Use proper DaisyUI components.

## No Custom JavaScript

Embrace the power of HTMX. Do NOT write custom JavaScript for interactivity. HTMX provides declarative attributes for almost everything:

- Use `hx_trigger` for keyboard shortcuts (e.g., `hx_trigger="keydown[metaKey&&key=='Enter']"`)
- Use `hx_post`, `hx_get`, `hx_target`, `hx_swap` for all requests
- Use `hx_include` to include form values from other elements
- Use `hx-on::after-request` for post-request cleanup (clearing inputs, etc.)
- Use OOB swaps (`hx_swap_oob="true"`) for updating multiple parts of the page

If you find yourself writing inline JS event handlers or `<script>` tags for interactivity, stop and find the HTMX way. The only acceptable JS is minimal one-liners for things HTMX genuinely can't do (like `this.value = ''`).

Run `./dev lint` after finishing code changes to lint the code.