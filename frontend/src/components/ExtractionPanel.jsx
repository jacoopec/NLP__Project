function Field({ label, value }) {
  if (value === null || value === undefined || value === '' || (Array.isArray(value) && value.length === 0)) {
    return null;
  }

  return (
    <div className="field-row">
      <span>{label}</span>
      <strong>{Array.isArray(value) ? value.join(', ') : String(value)}</strong>
    </div>
  );
}

export default function ExtractionPanel({ extracted, debug }) {
  return (
    <aside className="extraction-panel">
      <h3>Extracted travel constraints</h3>
      {!extracted && <p className="muted">No extraction yet.</p>}
      {extracted && (
        <>
          <Field label="Starting location" value={extracted.start_location} />
          <Field label="Max distance" value={extracted.max_distance_km ? `${extracted.max_distance_km} km` : null} />
          <Field
            label="Max travel time"
            value={extracted.max_travel_time_minutes ? `${extracted.max_travel_time_minutes} minutes` : null}
          />
          <Field label="Trip duration" value={extracted.trip_duration} />
          <Field label="Preferred transport" value={extracted.preferred_transport} />
          <Field label="Avoided transport" value={extracted.avoided_transport} />
          <Field label="Preferences" value={extracted.preferences} />
          <Field label="Avoid terms" value={extracted.avoid_terms} />
        </>
      )}

      {debug && Object.keys(debug).length > 0 && (
        <details className="debug-details">
          <summary>Graph debug</summary>
          <pre>{JSON.stringify(debug, null, 2)}</pre>
        </details>
      )}
    </aside>
  );
}
