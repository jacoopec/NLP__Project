# Agentic Travel Planner — LangGraph + FastAPI + React

This is a full-stack exam-ready starter project for an **agentic AI travel planner**.

The system receives a natural language message such as:

> I am really euphoric!!!!!! let's gooo :))))) I want to live a great experience and feel alive, I want to leave Bologna for a weekend. And I don't even think about using my car! I can travel up to 90 km.

It then:

1. cleans the text and extracts structured travel constraints with a **spaCy NLP pipeline**;
2. validates that the essential information is present;
3. searches a local **ChromaDB RAG memory** containing only seeded user-review documents;
4. performs **real web search** with SerpApi to fill missing candidates and support real enrichment;
5. retrieves real web photos and reviews for each destination;
6. returns at least 3 real destination cards to the React frontend when enough real data is available.

There are **no hardcoded destination fallbacks**. The only hardcoded domain data are the local RAG seed documents in `backend/data/user_reviews_seed.json`, because they represent user reviews.

---

## Important design choices

### Removed emotion extraction

This version intentionally removes the emotion/vibe extraction module. The workflow focuses on:

- travel constraints;
- user preferences and avoided terms;
- RAG retrieval over user reviews;
- real web search and enrichment.

### No fake fallback data

If the system needs web data and `SERPAPI_API_KEY` is missing, the backend returns an error. It does **not** invent destinations, reviews, or photos.

If the external provider returns fewer than 3 complete results with both photo and reviews, the backend reports that it could not satisfy the requirement with real data.

---

## Project structure

```text
agentic-travel-exam/
  backend/
    app/
      main.py
      config.py
      schemas.py
      graph/
        travel_graph.py
      services/
        nlp_service.py
        rag_service.py
        serpapi_service.py
        travel_pipeline.py
      utils/
        geo.py
        text.py
    data/
      user_reviews_seed.json
    scripts/
      seed_chroma.py
    requirements.txt
    .env.example
  frontend/
    package.json
    index.html
    src/
      App.jsx
      main.jsx
      styles.css
      api.js
      components/
        ChatBox.jsx
        DestinationCard.jsx
        ExtractionPanel.jsx
    public/
      banner.svg
```

---

## Backend setup

From the project root:

```bash
cd backend
python -m venv .venv
```

Activate the environment.

On Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

On macOS/Linux:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

Create the environment file:

```bash
cp .env.example .env
```

Then edit `.env`:

```env
OPENAI_API_KEY=your_openai_key_here
SERPAPI_API_KEY=your_serpapi_key_here
```

Seed the local ChromaDB from the user-review documents:

```bash
python scripts/seed_chroma.py
```

Start the backend:

```bash
uvicorn app.main:app --reload --port 8000
```

Open:

```text
http://localhost:8000/docs
```

---

## Frontend setup

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the Vite URL printed by the terminal, usually:

```text
http://localhost:5173
```

---

## Required input behavior

The graph checks that the following essential information was extracted:

1. starting location;
2. how far the user is willing to go.

The distance can be expressed as:

- explicit distance, for example `80 km`, `50 kilometers`, `30 miles`;
- travel time, for example `1 hour`, `90 minutes`, `up to 2 hours`.

If one of these fields is missing, the graph stops and returns `status = "needs_input"` with messages for the frontend.

Example that will stop because the distance/time is missing:

```text
I want to leave Bologna for a weekend and I don't want to use my car.
```

Example that can continue:

```text
I want to leave Bologna for a weekend, avoid using my car, and travel up to 90 km. I like waterfalls, lakes and hikes.
```

---

## LangGraph workflow

```text
nlp
  ↓
validate
  ├── missing essential information → END
  ↓
rag
  ↓
web_search
  ↓
enrich_with_real_reviews_and_photos
  ↓
END
```

The graph is implemented in:

```text
backend/app/graph/travel_graph.py
```

---

## API contract

### Request

```http
POST /api/trips/plan
Content-Type: application/json
```

```json
{
  "prompt": "I want to leave Bologna for a weekend, avoid using my car, and travel up to 90 km. I like waterfalls and hikes."
}
```

### Response when more information is needed

```json
{
  "status": "needs_input",
  "messages": [
    "Please tell me how far you are willing to go, for example '80 km' or '2 hours'."
  ],
  "extracted": {
    "start_location": "Bologna"
  },
  "destinations": []
}
```

### Response when successful

```json
{
  "status": "ok",
  "messages": [],
  "extracted": {
    "start_location": "Bologna",
    "max_distance_km": 90.0,
    "preferred_transport": null,
    "avoided_transport": ["car"],
    "preferences": ["waterfalls", "hikes"]
  },
  "destinations": [
    {
      "name": "...",
      "source": "rag+web" ,
      "photo_url": "https://...",
      "reviews": [
        {
          "text": "...",
          "author": "...",
          "rating": 5.0,
          "url": "..."
        }
      ]
    }
  ]
}
```

---

## Notes for the exam presentation

You can explain the project as an agentic workflow because the system does not simply call a single model. It uses a stateful graph with explicit decisions:

- extract structured information from messy text;
- stop early if essential constraints are missing;
- retrieve from local user memory first;
- call real web search to fill missing candidates and collect external evidence;
- enrich each candidate with real web photos and web reviews;
- return structured results to the frontend.

The RAG memory represents personal/social experience data. The web search acts as a second source when the local memory is not enough.

---

## Troubleshooting

### `SERPAPI_API_KEY is missing`

This is expected if you did not configure SerpApi. The project refuses to create fake web results.

### `OPENAI_API_KEY is missing`

OpenAI is used for Chroma embeddings. Seed the database only after setting the key.

### spaCy model missing

Run:

```bash
python -m spacy download en_core_web_sm
```

### RAG returns no results

Check that you ran:

```bash
python scripts/seed_chroma.py
```

You can also inspect `backend/data/user_reviews_seed.json` and add more real user-review documents.
