import { useState } from 'react';
import { Compass, MapPinned } from 'lucide-react';
import { planTrip } from './api.js';
import ChatBox from './components/ChatBox.jsx';
import DestinationCard from './components/DestinationCard.jsx';
import ExtractionPanel from './components/ExtractionPanel.jsx';

export default function App() {
  const [response, setResponse] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(prompt) {
    setLoading(true);
    setError('');
    setResponse(null);

    try {
      const data = await planTrip(prompt);
      setResponse(data);
      if (data.status === 'error') {
        setError(data.messages?.join(' ') || 'The pipeline returned an error.');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const destinations = response?.destinations || [];

  return (
    <div className="app-shell">
      <header className="hero">
        <div className="hero-overlay" />
        <div className="hero-content">
          <div className="badge"><Compass size={16} /> LangGraph travel agent</div>
          <h1>Input your vibes, I'll tell you where you want to go!</h1>
          <p>
            A real retrieval pipeline: spaCy extraction, ChromaDB user memories, web search,
            photos and reviews.
          </p>
        </div>
      </header>

      <main className="layout">
        <section className="left-column">
          <ChatBox onSubmit={handleSubmit} loading={loading} />
          {error && <div className="error-box">{error}</div>}
          {response?.status === 'needs_input' && (
            <div className="needs-input-box">
              {response.messages.map((message, index) => (
                <p key={index}>{message}</p>
              ))}
            </div>
          )}
        </section>

        <section className="right-column">
          <ExtractionPanel extracted={response?.extracted} debug={response?.debug} />
        </section>
      </main>

      <section className="results-section">
        <div className="section-title">
          <MapPinned size={22} />
          <h2>Suggested destinations</h2>
        </div>

        {!response && !loading && (
          <p className="muted">Results will appear here after the agent completes the graph.</p>
        )}

        {loading && <div className="loading-card">Searching local reviews first, then real web sources if needed...</div>}

        {destinations.length > 0 && (
          <div className="cards-grid">
            {destinations.map((destination, index) => (
              <DestinationCard key={`${destination.name}-${index}`} destination={destination} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
