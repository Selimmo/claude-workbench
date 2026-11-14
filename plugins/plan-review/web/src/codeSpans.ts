// Backticks only: no bold, links or lists, and no markdown library.

export interface Span {
  code: boolean
  text: string
}

/** Cuts text into plain and code parts at each pair of backticks. A lone or empty pair stays as written. */
export function codeSpans(text: string): Span[] {
  const spans: Span[] = []
  const add = (code: boolean, part: string) => {
    const last = spans[spans.length - 1]
    if (!code && last && !last.code) last.text += part
    else if (part) spans.push({ code, text: part })
  }
  let rest = text
  for (;;) {
    const open = rest.indexOf('`')
    const close = open < 0 ? -1 : rest.indexOf('`', open + 1)
    if (close < 0) break
    add(false, rest.slice(0, open))
    if (close === open + 1) add(false, '``')
    else add(true, rest.slice(open + 1, close))
    rest = rest.slice(close + 1)
  }
  add(false, rest)
  return spans
}
