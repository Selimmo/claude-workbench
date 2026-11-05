/** The run's files that are there but broken, each line naming its file; nothing when all read. */
export function BrokenFilesBanner({ errors }: { errors: string[] }) {
  if (errors.length === 0) return null
  return (
    <div role="alert" aria-label="Broken files" className="broken-files">
      <ul>
        {errors.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
    </div>
  )
}
