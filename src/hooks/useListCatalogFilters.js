import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from '../api/client.js';
import { catalogCountries } from '../utils/catalogFilterOptions.js';
import { emptyListFilters } from '../utils/listCatalogFilters.js';
import { yearRangeDraft } from '../features/search/advancedSearchModel.js';

export default function useListCatalogFilters() {
  const [filters, setFilters] = useState(emptyListFilters);
  const [appliedYears, setAppliedYears] = useState({ yearFrom: '', yearTo: '' });
  const [countries, setCountries] = useState(catalogCountries);
  const yearDraft = yearRangeDraft(filters.yearFrom, filters.yearTo);
  useEffect(() => {
    const controller = new AbortController();
    fetchJson('/api/tmdb/filter-options', { signal: controller.signal }).then(data => {
      const options = data.countries?.filter(option => option.value && option.label);
      if (options?.length) setCountries([{ value: '', label: 'All countries' }, ...options]);
    }).catch(() => {}); // Built-in choices remain usable if configuration is offline.
    return () => controller.abort();
  }, []);
  const effective = useMemo(() => ({ ...filters, ...appliedYears }), [filters, appliedYears]);
  function changeFilter(key, value) {
    const next = { ...filters, [key]: value };
    setFilters(next);
    const years = yearRangeDraft(next.yearFrom, next.yearTo);
    if (years.ready && (key === 'yearFrom' || key === 'yearTo')) setAppliedYears({ yearFrom: years.from, yearTo: years.to });
  }
  function resetFilters() { setFilters(emptyListFilters()); setAppliedYears({ yearFrom: '', yearTo: '' }); }
  return { filters, effective, countries, yearDraft, changeFilter, resetFilters };
}
