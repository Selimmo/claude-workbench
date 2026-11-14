import { codeSpans } from './codeSpans'

/** Written text, with each part in backticks as a small code chip. Fits inside any paragraph or list line. */
export function Prose({ text }: { text: string }) {
  return (
    <>
      {codeSpans(text).map((span, i) =>
        span.code ? (
          <code key={i} className="inline-code">
            {span.text}
          </code>
        ) : (
          span.text
        ),
      )}
    </>
  )
}
