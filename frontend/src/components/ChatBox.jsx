import { useState } from 'react';
import { Send } from 'lucide-react';

const INITIAL_MESSAGE =
  'Describe your vibes, where you currently are, how far are you willing to go, preferred mean of transport and how long your trip will last';

export default function ChatBox({ onSubmit, loading }) {
  const [prompt, setPrompt] = useState('');

  function submit(event) {
    event.preventDefault();
    if (!prompt.trim() || loading) return;
    onSubmit(prompt.trim());
  }

  return (
    <div className="chat-panel">
      <div className="assistant-message">{INITIAL_MESSAGE}</div>
      <form onSubmit={submit}>
        <textarea
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          placeholder="Example: I want to leave Bologna for a weekend, avoid using my car, and travel up to 90 km. I like waterfalls, lakes and hikes."
          rows={6}
        />
        <button type="submit" disabled={loading || !prompt.trim()}>
          <Send size={18} />
          {loading ? 'Running graph...' : 'Plan my trip'}
        </button>
      </form>
    </div>
  );
}
