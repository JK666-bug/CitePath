import type { Question } from '../course/types'

export default function QuestionCard({
  question,
  index,
  answer,
  onChange,
}: {
  question: Question
  index: number
  answer: string
  onChange: (answer: string) => void
}) {
  return (
    <fieldset
      className="panel question-card"
      id={question.id}
      tabIndex={-1}
    >
      <legend className="sr-only">
        Question {index + 1}
      </legend>

      <div className="actions spread">
        <span className="eyebrow">
          Question {index + 1}
        </span>

        <span className="badge">
          {question.kind === 'mcq'
            ? 'Multiple choice'
            : 'Short answer'}
        </span>
      </div>

      <h2>{question.prompt}</h2>

      {question.kind === 'mcq' ? (
        <div className="question-options">
          {question.options.map(
            (option, optionIndex) => (
              <label
                key={option}
                className={
                  answer === option
                    ? 'selected'
                    : ''
                }
              >
                <input
                  type="radio"
                  name={question.id}
                  checked={answer === option}
                  value={option}
                  onChange={() =>
                    onChange(option)
                  }
                />

                <span className="option-letter">
                  {String.fromCharCode(
                    65 + optionIndex,
                  )}
                </span>

                <span>{option}</span>
              </label>
            ),
          )}
        </div>
      ) : (
        <label className="field">
          <span className="sr-only">
            Your answer to question
            {' '}{index + 1}
          </span>

          <textarea
            value={answer}
            maxLength={5000}
            rows={5}
            onChange={(event) =>
              onChange(event.target.value)
            }
            placeholder="Explain your reasoning in your own words."
          />
        </label>
      )}
    </fieldset>
  )
}