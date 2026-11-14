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
