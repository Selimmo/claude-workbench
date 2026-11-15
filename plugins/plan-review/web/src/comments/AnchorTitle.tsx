import type { AnchorName } from '../anchorNames'

/** The top of a comment card: what the comment is on, in words, with the raw id in grey under it. */
export function AnchorTitle({ name }: { name: AnchorName }) {
  return (
    <div className="anchor-title">
      <span className="anchor-name" title={name.full}>
        {name.short}
      </span>
      <code className="anchor-id">{name.id}</code>
    </div>
  )
}
