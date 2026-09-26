import { AlertTriangle, BookOpen, Film, Loader2, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { fetchJson } from '../api/client.js';
import { cx } from '../utils/appUtils.js';

export function usePersonBiography() {
  const [personBio, setPersonBio] = useState(null);
  const request = useRef(null);
  useEffect(() => () => request.current?.abort(), []);

  async function openPersonBio(role, person) {
    request.current?.abort();
    if (!person?.id) {
      setPersonBio({ loading: false, error: 'No TMDB person ID is available for this credit.', person, role });
      return;
    }
    const controller = new AbortController();
    request.current = controller;
    setPersonBio({ loading: true, error: '', person, role });
    try {
      const data = await fetchJson(`/api/tmdb/person?person_id=${encodeURIComponent(person.id)}`, { signal: controller.signal });
      if (!controller.signal.aborted) setPersonBio({ loading: false, error: '', person, role, data });
    } catch (error) {
      if (!controller.signal.aborted) setPersonBio({ loading: false, error: error.message, person, role });
    }
  }

  function closePersonBio() {
    request.current?.abort();
    setPersonBio(null);
  }

  return { personBio, openPersonBio, closePersonBio };
}

export function PersonCreditCard({ person, role, canBrowse, onBrowse, onDiscover, onBio }) {
  const isDirector = role === 'director' || role === 'creator';
  const className = cx('person-card', isDirector && 'director-person', !canBrowse && 'discover-person-static', canBrowse && 'person-credit-browse');
  const browseLabel = person.character || person.role || (isDirector ? 'Director' : 'Cast');
  const canDiscover = Boolean(onDiscover && person?.id);

  function browse() {
    if (canBrowse) onBrowse(role, person);
  }

  function handleKeyDown(event) {
    if (event.target !== event.currentTarget) return;
    if (!canBrowse || (event.key !== 'Enter' && event.key !== ' ')) return;
    event.preventDefault();
    browse();
  }

  return (
    <div className={className} role={canBrowse ? 'button' : undefined} tabIndex={canBrowse ? 0 : undefined}
      onClick={canBrowse ? browse : undefined} onKeyDown={handleKeyDown}>
      <button type="button" className="person-bio-button" onClick={(event) => { event.stopPropagation(); onBio(role, person); }}
        aria-label={`Open biography for ${person.name}`} title="Biography"><BookOpen size={14} /></button>
      {canDiscover && <button type="button" className="person-discover-button" onClick={(event) => { event.stopPropagation(); onDiscover(role, person); }}
        aria-label={`Open filmography for ${person.name}`} title="Filmography"><Film size={14} /></button>}
      <PersonAvatar person={person} />
      <strong dir="auto">{person.name}</strong>
      <small>{browseLabel}</small>
    </div>
  );
}

export function PersonBioModal({ state, onClose }) {
  const data = state.data || {};
  const fallback = state.person || {};
  const name = data.name || fallback.name || 'TMDB person';
  const profileUrl = data.profile_url || fallback.profile_url || '';
  const roleLabel = { director: 'Director', writer: 'Writer', creator: 'Creator' }[state.role] || 'Actor';
  const biography = String(data.biography || '').trim();
  const facts = [data.known_for_department || roleLabel, data.birthday ? `Born ${data.birthday}` : '',
    data.deathday ? `Died ${data.deathday}` : '', data.place_of_birth || ''].filter(Boolean);
  const initial = String(name).trim().slice(0, 1).toUpperCase() || '?';

  const modal = (
    <div className="modal-backdrop person-bio-backdrop" role="presentation" onClick={onClose}>
      <section className="person-bio-dialog" role="dialog" aria-modal="true" aria-label={`Biography for ${name}`}
        onClick={(event) => event.stopPropagation()}>
        <div className="dialog-header person-bio-header">
          <div><p className="screen-kicker">{roleLabel} profile</p><h2>{name}</h2></div>
          <button type="button" className="inspector-close" onClick={onClose} aria-label="Close biography"><X size={18} /></button>
        </div>
        <div className="person-bio-content">
          <div className="person-bio-photo">{profileUrl ? <img src={profileUrl} alt={`${name} portrait`} /> : <span>{initial}</span>}</div>
          <div className="person-bio-copy">
            {state.loading ? <div className="dialog-loading person-bio-loading"><Loader2 size={18} className="spin" />
              <span className="dialog-loading-copy"><strong>Loading TMDB profile...</strong><small>Fetching biography and portrait.</small></span>
            </div> : state.error ? <p className="dialog-error person-bio-error"><AlertTriangle size={15} /> {state.error}</p> : <>
              {facts.length ? <div className="person-bio-facts">{facts.map((fact) => <span key={fact}>{fact}</span>)}</div> : null}
              <p>{biography || 'No biography available from TMDB.'}</p>
            </>}
          </div>
        </div>
      </section>
    </div>
  );
  return typeof document === 'undefined' ? modal : createPortal(modal, document.body);
}

function PersonAvatar({ person }) {
  const initial = String(person?.name || '?').trim().slice(0, 1).toUpperCase() || '?';
  return <span className="person-avatar" aria-hidden="true">
    {person?.profile_url ? <img src={person.profile_url} alt="" loading="lazy" /> : initial}
  </span>;
}
