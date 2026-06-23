# I18n And Theme

The frontend uses static JSON locale files and CSS custom properties.

## Locale Files

- English: `manager/frontend/src/locales/en.json`
- Simplified Chinese: `manager/frontend/src/locales/zh-CN.json`

When adding text:

1. Add the key to `en.json`.
2. Add the same key to `zh-CN.json`.
3. Use `t("path.to.key")` in frontend code.
4. Run `node manager/frontend/tests/ui-foundation.test.mjs`.

The locale test asserts both files expose the same flattened key set.

## Theme Modes

Theme modes are implemented in `manager/frontend/src/theme-core.mjs`:

- `light`: always applies the light palette.
- `dark`: always applies the dark palette.
- `system`: resolves through `prefers-color-scheme`.

The selected mode is stored in browser localStorage. The resolved theme is
written to `document.documentElement.dataset.theme`, and CSS variables in
`manager/frontend/styles.css` provide the palette.

## Defaults

WebUI preference defaults are stored in manager config:

```yaml
webui:
  default_language: en
  default_theme: system
```

Users can override these in the browser without changing the YAML file.
