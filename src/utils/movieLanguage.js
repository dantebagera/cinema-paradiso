const arabicText = /[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff]/u;

export function isArabicMovie(movie, details) {
  const original = String(movie?.original_language || details?.original_language || '').trim().toLowerCase();
  const language = original || String(movie?.language || details?.language || '').trim().toLowerCase();
  return ['ar', 'ara', 'arabic', 'العربية'].includes(language) || language.startsWith('ar-');
}

export function movieDisplayTitle(movie, details, localized) {
  if (isArabicMovie(movie, details)) {
    return [localized?.title, movie?.original_title, details?.original_title, movie?.title, details?.title]
      .find(value => typeof value === 'string' && arabicText.test(value)) || movie?.title || details?.title || '';
  }
  return localized?.title?.trim() || movie?.title || details?.title || '';
}
