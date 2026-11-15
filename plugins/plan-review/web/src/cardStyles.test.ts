import css from './styles.css?raw'

interface Rule {
  selectors: string[]
  decls: Map<string, string>
}

/** The style sheet's plain rules (media blocks are flattened), comments removed. */
function rules(): Rule[] {
  const text = css.replace(/\/\*[\s\S]*?\*\//g, '')
  return [...text.matchAll(/([^{}]+)\{([^{}]*)\}/g)].map(([, head, body]) => ({
    selectors: head
      .trim()
      .split(',')
      .map((s) => s.trim()),
    decls: new Map(
      body
        .split(';')
        .map((d) => d.split(/:(.*)/s).map((x) => x.trim()))
        .filter(([name, value]) => name && value)
        .map(([name, value]) => [name, value] as const),
    ),
  }))
}

/** Everything one exact selector sets, over all of its rules. */
function declared(selector: string): Map<string, string> {
  const merged = new Map<string, string>()
  for (const r of rules())
    if (r.selectors.includes(selector)) for (const [k, v] of r.decls) merged.set(k, v)
  return merged
}

const CARD = ['.thread-card', '.class-details', '.card-top', '.messages', '.details-', '.member-']

test('every floating card takes its type sizes and spacing from one shared scale', () => {
  const scale = [
    '--card-title',
    '--card-text',
    '--card-code',
    '--card-small',
    '--card-gap',
    '--card-pad',
    '--card-leading',
  ]
  for (const name of scale) {
    expect(css.match(new RegExp(`${name}:`, 'g'))).toHaveLength(1)
    expect(declared('.thread-card').has(name)).toBe(true)
  }
  const scoped = [
    '.thread-card .hint',
    '.thread-card .badge',
    '.thread-card .error',
    '.thread-card .draft-actions button.link',
    '.thread-card button.icon',
  ]
  for (const selector of scoped)
    expect(declared(selector).get('font-size')).toMatch(/^var\(--card-/)
  for (const r of rules())
    for (const selector of r.selectors)
      if (CARD.some((prefix) => selector.startsWith(prefix)) && r.decls.has('font-size'))
        expect(r.decls.get('font-size'), selector).toMatch(/^var\(--card-/)
})

test('a card scrolls its body when content is too tall or too wide, and keeps its top line in view', () => {
  const card = declared('.thread-card')
  expect(card.has('max-height')).toBe(true)
  expect(card.get('overflow')).toBe('hidden')
  expect(card.has('width')).toBe(true)
  expect(card.has('max-width')).toBe(true)
  expect(declared('.card-top').get('flex')).toBe('none')
  const body = declared('.card-body')
  expect(body.get('overflow-y')).toBe('auto')
  expect(body.get('min-height')).toBe('0')
  expect(body.get('overflow-x')).toBe('auto')
  expect(body.get('min-width')).toBe('0')
  const signature = declared('.member-signature')
  expect(signature.get('white-space')).toBe('pre')
  expect(signature.get('overflow-x')).toBe('auto')
  expect(signature.get('overflow-wrap')).toBeUndefined()
  for (const r of rules())
    for (const selector of r.selectors)
      if (['.messages', '.member-group', '.member-details'].some((p) => selector.startsWith(p)))
        expect(r.decls.has('overflow-y'), selector).toBe(false)
})

test("the popup's kind label stays beside the title, with or without a comment icon", () => {
  // Free space goes after the kind label, so Close (and the icon, when there is one) sit at the right.
  expect(declared('.card-top .kind').get('margin-right')).toBe('auto')
  expect(declared('.class-details .card-top .comment-icon').get('margin-left')).toBe('0')
})

test("the popup title's status only colours the class name, with no background or border", () => {
  for (const status of ['added', 'modified', 'removed']) {
    const title = declared(`.details-title[data-status='${status}']`)
    expect(title.get('background'), status).toBe('none')
    expect(title.get('border-left'), status).toBe('0')
  }
})

const THEMES = [':root', ":root:not([data-theme='light'])", ":root[data-theme='dark']"]

test('the flowchart colours are set in every theme block', () => {
  for (const theme of THEMES)
    for (const name of ['--flow-fill', '--flow-line', '--tag-bg'])
      expect(declared(theme).has(name), `${theme} ${name}`).toBe(true)
})

test('a flowchart step takes its outline and its tint from its status', () => {
  for (const status of ['added', 'modified', 'removed']) {
    const shape = declared(`.flow-node[data-status='${status}'] .shape`)
    expect(shape.get('stroke'), status).toBe(`var(--${status})`)
    expect(shape.get('fill'), status).toBe(`var(--${status}-bg)`)
  }
  const unchanged = declared(".flow-node[data-status='unchanged'] .shape")
  expect(unchanged.get('stroke')).toBe('var(--flow-line)')
  expect(unchanged.get('fill')).toBe('var(--flow-fill)')
  expect(declared('.flow-node .shape').get('stroke-width')).toBe('2')
  expect(declared(".flow-node[data-status='removed'] .shape").get('stroke-dasharray')).toBeTruthy()
  expect(declared(".flow-node[data-status='removed'] text").get('text-decoration')).toBe(
    'line-through',
  )
})

test('flowchart text is 500 13px, tags are 600 11px on the tag colour, both in the measured family', () => {
  const flow = declared('.flow-node text')
  const tag = declared('.tag text')
  expect([flow.get('font-weight'), flow.get('font-size')]).toEqual(['500', '13px'])
  expect([tag.get('font-weight'), tag.get('font-size')]).toEqual(['600', '11px'])
  // The family is inherited from :root, which is what measure.ts measures in.
  for (const d of [flow, tag]) {
    expect(d.has('font')).toBe(false)
    expect(d.has('font-family')).toBe(false)
  }
  expect(declared('.tag rect').get('fill')).toBe('var(--tag-bg)')
  expect(declared('.tag rect').get('stroke')).toBe('var(--muted)')
})

test('a main line is the accent colour and thicker than a plain one, and thicker still on hover', () => {
  const plain = Number(declared('.edge .line').get('stroke-width'))
  const main = declared(".edge[data-main='true'] .line")
  const hover = declared(".commentable .edge[data-main='true']:hover .line")

  expect(main.get('stroke')).toBe('var(--accent)')
  expect(Number(main.get('stroke-width'))).toBeGreaterThan(plain)
  expect(Number(hover.get('stroke-width'))).toBeGreaterThan(Number(main.get('stroke-width')))
  expect(declared('marker.main path').get('fill')).toBe('var(--accent)')
})

test('a main line still shows when a test points at it or a revision changed it', () => {
  const main = Number(declared(".edge[data-main='true'] .line").get('stroke-width'))
  const focused = declared(".edge[data-main='true'][data-focused='true'] .line")
  const revised = declared(".edge[data-main='true'][data-revised='true'] .line")

  expect(focused.get('stroke')).toBe('var(--accent)')
  expect(Number(focused.get('stroke-width'))).toBeGreaterThan(main)
  expect(Number(revised.get('stroke-width'))).toBeGreaterThan(main)
})

test('the tag of a focused line keeps its thin border', () => {
  const tag = declared("g[data-focused='true'] .tag rect")

  expect(tag.get('stroke-width')).toBe('1')
  expect(tag.get('stroke')).toBe('var(--muted)')
})

test('hovering, focusing or revising a step shows on its shape', () => {
  expect(declared('.commentable .flow-node:hover .shape').get('stroke')).toBe('var(--accent)')
  expect(declared(".flow-node[data-focused='true'] .shape").get('stroke')).toBe('var(--accent)')
  expect(declared(".flow-node[data-revised='true'] .shape").has('stroke-width')).toBe(true)
})

test('the close button shows its focus ring only for the keyboard', () => {
  expect(declared('button.icon').get('outline')).toBe('none')
  expect(declared('button.icon:focus-visible').get('outline')).toMatch(/var\(--accent\)/)
  expect(declared('button.icon:focus').has('outline')).toBe(false)
  expect(declared('.class-details:focus').get('outline')).toBe('none')
})

function position(selector: string): number {
  return rules().findIndex((r) => r.selectors.includes(selector))
}

test('a revised flowchart step is outlined in the accent colour', () => {
  expect(declared(".flow-node[data-revised='true'] .shape").get('stroke')).toBe('var(--accent)')
})

test('a focused and revised step keeps the focused width', () => {
  const revised = position(".flow-node[data-revised='true'] .shape")
  const focused = position(".flow-node[data-focused='true'] .shape")
  expect(revised).toBeGreaterThanOrEqual(0)
  expect(focused).toBeGreaterThan(revised)
})

test('a focused and revised main line keeps the focused width', () => {
  const revised = position(".edge[data-main='true'][data-revised='true'] .line")
  const focused = position(".edge[data-main='true'][data-focused='true'] .line")
  expect(revised).toBeGreaterThanOrEqual(0)
  expect(focused).toBeGreaterThan(revised)
})
