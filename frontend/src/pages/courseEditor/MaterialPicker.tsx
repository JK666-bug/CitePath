import {
  FileText,
  Upload,
  X,
} from 'lucide-react'

export function fileKey(file: File) {
  return (
    `${file.name}:` +
    `${file.size}:` +
    file.lastModified
  )
}

export default function MaterialPicker({
  files,
  onChange,
  disabled = false,
}: {
  files: File[]
  onChange: (files: File[]) => void
  disabled?: boolean
}) {
  return (
    <div className="material-picker">
      <label className="upload-zone">
        <Upload
          size={22}
          strokeWidth={1.4}
        />

        <strong>
          Add course materials
        </strong>

        <span>
          Choose one or more PDF files
        </span>

        <input
          type="file"
          accept=".pdf,application/pdf"
          multiple
          disabled={disabled}
          onChange={(event) => {
            const selected = [
              ...files,
              ...Array.from(
                event.target.files || [],
              ),
            ]

            onChange(
              selected.filter(
                (file, index) =>
                  selected.findIndex(
                    (item) =>
                      fileKey(item) ===
                      fileKey(file),
                  ) === index,
              ),
            )

            event.target.value = ''
          }}
        />
      </label>

      {files.length > 0 && (
        <ul className="pending-files">
          {files.map((file) => (
            <li key={fileKey(file)}>
              <FileText size={15} />

              <span>{file.name}</span>

              <small>
                {Math.max(
                  1,
                  Math.round(
                    file.size / 1024,
                  ),
                )}{' '}
                KB
              </small>

              <button
                className="icon-button"
                type="button"
                aria-label={
                  `Remove ${file.name}`
                }
                disabled={disabled}
                onClick={() =>
                  onChange(
                    files.filter(
                      (item) =>
                        fileKey(item) !==
                        fileKey(file),
                    ),
                  )
                }
              >
                <X size={14} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}