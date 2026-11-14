import type { Plan } from '../plan'
import { filesByKind } from '../viewModels'
import { Prose } from '../Prose'

export function FilesTab({ plan }: { plan: Plan }) {
  return filesByKind(plan).map((group) => (
    <div key={group.kind} className="group">
      <h2>{group.label}</h2>
      <ul className="rows">
        {group.files.map((file) => (
          <li key={file.id} data-element-id={file.id} data-status={file.change}>
            <span className="change">{file.change}</span>
            <code>{file.path}</code>
            <span className="reason">
              <Prose text={file.reason} />
            </span>
          </li>
        ))}
      </ul>
    </div>
  ))
}
