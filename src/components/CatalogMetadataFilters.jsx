import { Select, Input } from './ui/FormField.jsx';
import WorkspaceYearRange from './WorkspaceYearRange.jsx';
import { catalogCountries, movieGenres } from '../utils/catalogFilterOptions.js';

export const catalogSortChoices = [
  ['auto', 'Default order'], ['popularity.desc', 'Popularity'], ['vote_average.desc', 'Rating'],
  ['vote_count.desc', 'Most voted'], ['primary_release_date.desc', 'Release date'], ['title.asc', 'Title A-Z']
];

// Shared fields; each workspace owns its data source and filter application.
export default function CatalogMetadataFilters({ values, onChange, genres = movieGenres, countries = catalogCountries, prefix = '', yearError, yearErrorId, countryLabel = 'Production country', sortLabel = 'Sort results', sortChoices = catalogSortChoices }) {
  const label = name => `${prefix}${name}`;
  const select = (key, name, choices) => <Select aria-label={label(name)} value={values[key]} onChange={event => onChange(key, event.target.value)}>{choices.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</Select>;
  return <>
    {select('genre', 'Genre', genres)}
    {select('sort', sortLabel, sortChoices.map(([value, name]) => ({ value, label: name })))}
    {select('country', countryLabel, countries)}
    {select('minVotes', 'Minimum votes', [{ value: '0', label: 'Any votes' }, ...[500, 1000, 5000, 10000].map(value => ({ value: String(value), label: `${value.toLocaleString('en-US')}+ votes` }))])}
    <WorkspaceYearRange>{['yearFrom', 'yearTo'].map((key, index) => <Input key={key} className="library-mini-input" aria-label={label(index ? 'Year to' : 'Year from')} aria-describedby={yearError ? yearErrorId : undefined} aria-invalid={Boolean(yearError)} placeholder={index ? 'Year to' : 'Year from'} inputMode="numeric" maxLength={4} value={values[key]} onChange={event => onChange(key, event.target.value)} />)}</WorkspaceYearRange>
    {select('minRating', 'Minimum rating', [{ value: '0', label: 'Any rating' }, ...[6, 7, 8, 8.5].map(value => ({ value: String(value), label: `${value}+` }))])}
  </>;
}
