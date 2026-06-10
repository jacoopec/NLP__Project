import { useState } from 'react';
import { ExternalLink, Star } from 'lucide-react';

export default function DestinationCard({ destination }) {
  const [open, setOpen] = useState(false);

  return (
    <article className="destination-card">
      <button className="card-main" onClick={() => setOpen(!open)} aria-expanded={open}>
        {destination.photo_url ? (
          <img src={destination.photo_url} alt={destination.name} />
        ) : (
          <div className="photo-missing">No web photo returned</div>
        )}

        <div className="card-body">
          <div className="source-pill">{destination.source}</div>
          <h3>{destination.name}</h3>
          {destination.description && <p>{destination.description}</p>}
          <div className="meta-row">
            {destination.rating && (
              <span><Star size={15} /> {destination.rating}</span>
            )}
            {destination.review_count && <span>{destination.review_count} reviews</span>}
            {destination.distance_km && <span>{destination.distance_km} km away</span>}
          </div>
          {destination.address && <small>{destination.address}</small>}
        </div>
      </button>

      {open && (
        <div className="reviews-panel">
          <h4>Reviews and evidence</h4>
          {destination.reviews?.length > 0 ? (
            destination.reviews.map((review, index) => (
              <blockquote key={`${review.text}-${index}`}>
                <p>{review.text}</p>
                <footer>
                  {review.author && <span>{review.author}</span>}
                  {review.rating && <span>Rating: {review.rating}</span>}
                  <span>{review.source}</span>
                </footer>
              </blockquote>
            ))
          ) : (
            <p className="muted">No reviews returned by the web provider.</p>
          )}

          <div className="link-row">
            {destination.url && (
              <a href={destination.url} target="_blank" rel="noreferrer">
                Open source <ExternalLink size={15} />
              </a>
            )}
          </div>
        </div>
      )}
    </article>
  );
}
