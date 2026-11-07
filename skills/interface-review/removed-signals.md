# Removed signals

What to look for on the `-` side of a hunk and which domain owns the judgement. A row here is a lead, never a finding. Check the removal against its domain in `SKILL.md` §7 and report it only when the interface concretely got worse.

| Removed from the `-` side | Domain | What to check |
| --- | --- | --- |
| `aria-label`, `aria-labelledby`, `aria-describedby`, `aria-live`, `role=` | `Accessibility` | The control or region lost its accessible name, description, or announcement |
| `alt=`, `<label`, `for=`, `scope=` | `Accessibility` | Image, field, or table cell lost its programmatic association |
| `<button>`, `<a>`, `<nav>`, `<main>`, `<ul>` replaced by `div` or `span` | `Accessibility` | Keyboard and assistive-technology behavior was traded for styling |
| `:focus-visible`, `:focus`, `outline`, `tabindex` | `Accessibility` | Keyboard users lost the focus indicator or the element left the tab order |
| `prefers-reduced-motion`, `prefers-contrast` | `Accessibility` | Motion or contrast now ignores the user's system preference |
| Logical properties swapped for `left` / `right` | `Layout` | Direction-aware layout was dropped (only when the repo localizes to RTL) |
| `lang=`, `dir=` | `Typography` | Language metadata or text direction was dropped |
| `text-wrap`, `line-clamp`, `overflow-wrap`, `tabular-nums`, `font-feature-settings` | `Typography` | Text rendering, wrapping, or numeral alignment silently changed |
| A color token swapped for a literal, or a token swapped for a lighter one | `Colors` | The rendered contrast pair may now fail; measure it |
| A user-facing string deleted or shortened | `Writing` | A label, error, or action affordance lost the information it carried. Supplementary summaries (counts, progress, totals) removed by a deliberate redesign are not regressions unless a product spec requires them and no supported path shows the value |

## Equivalent replacements

These clear the signal. Check for them before routing anything, or the report fills with refactors reported as regressions:

- `aria-label` giving way to `aria-labelledby` pointing at visible text.
- An explicit `role` dropped because the element became the native equivalent, `role="button"` going as a `div` becomes a `<button>`.
- `outline` replaced by a `box-shadow` focus ring that still meets the focus-indicator rule.
- `tabindex="0"` dropped from an element that is now natively focusable.
- A color literal replaced by a token that measures the same rendered pair.
- A string moved into the translation catalogue rather than deleted.

## Searching the removed side

Restrict the search to deleted lines so additions do not mask a removal:

```bash
git diff -U0 "$BASE"...HEAD -- '*.tsx' '*.css' | grep -E '^-[^-]' | grep -E 'aria-|role=|alt=|focus|tabindex|prefers-'
```

Read the surrounding hunk before deciding. A removed attribute is meaningless without the element it came from, and `-U0` deliberately hides that context.
