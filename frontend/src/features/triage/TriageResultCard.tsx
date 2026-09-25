import type { TriageResult } from './triageApi'

interface Props {
  result: TriageResult
  specialtyName: string
  /** Accessible name; history entries use a different one from the current result. */
  label?: string
}

/**
 * The only place a triage urgency is displayed. It takes the whole result, so the safety
 * disclaimer always travels with the urgency and cannot be left out.
 */
export default function TriageResultCard({
  result,
  specialtyName,
  label = 'Triage result',
}: Props) {
  const overridden = result.overriddenUrgency !== null && result.overriddenUrgency !== undefined
  return (
    <section aria-label={label} className={`triage triage-${result.effectiveUrgency}`}>
      <p>
        <span>Urgency: </span>
        <strong className="urgency">{result.effectiveUrgency}</strong>
        {result.source === 'red_flag' && <span className="badge badge-emergency">Safety rule</span>}
      </p>
      {overridden && (
        <div className="override-compare">
          <p>{`AI suggestion: ${result.urgency}`}</p>
          <p>{`Staff override: ${result.overriddenUrgency}`}</p>
          <p>Reason: {result.overrideReason}</p>
        </div>
      )}
      <dl>
        <dt>Suggested specialty</dt>
        <dd>{specialtyName}</dd>
        <dt>Confidence</dt>
        <dd>{`${Math.round(result.confidenceScore * 100)}%`}</dd>
      </dl>
      <p className="disclaimer">{result.disclaimer}</p>
    </section>
  )
}
