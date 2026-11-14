import { useState } from 'react';
import { Play, Search, X } from 'lucide-react';
import Button, { StreamButton } from '../../components/ui/Button.jsx';
import Badge from '../../components/ui/Badge.jsx';
import FormField, { Input, Select } from '../../components/ui/FormField.jsx';
import DialogShell, { DialogActions } from '../../components/ui/DialogShell.jsx';
import SectionTabs, { SectionTab } from '../../components/ui/SectionTabs.jsx';
import Pagination from '../../components/Pagination.jsx';
import WorkspaceSelectionBar from '../../components/WorkspaceSelectionBar.jsx';
import WorkspaceEmptyState from '../../components/WorkspaceEmptyState.jsx';
import SearchField from '../search/SearchField.jsx';

// The reference renders production owners. Sample state is local to this page.
export default function UIReference() {
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState(0);
  const [tab, setTab] = useState('Movies');
  const [query, setQuery] = useState('');
  const [dialog, setDialog] = useState(false);
  const [saved, setSaved] = useState(0);
  return <div className="sg-component-stack" data-testid="shared-ui-reference">
    <div className="sg-button-row">
      <Button type="button" variant="primary">Primary</Button>
      <Button type="button">Secondary</Button>
      <Button type="button" variant="play" icon={Play}>Play</Button>
      <StreamButton type="button" />
      <Button type="button" variant="danger">Delete</Button>
      <Button type="button" variant="ai">AI action</Button>
      <Button type="button" size="compact" icon={Search}>Find sources</Button>
      <Button type="button" disabled>Unavailable</Button>
      <Button type="button" loading disabled>Working…</Button>
      <Button type="button" dir="auto">إضافة الفيلم إلى القائمة</Button>
    </div>
    <div className="sg-chip-row">
      <Badge kind="owned">Owned</Badge><Badge kind="status" tone="following">Following</Badge>
      <Badge kind="status" tone="warning">Low quality</Badge><Badge muted>English</Badge>
      <Badge size="compact">1080p WEB-DL</Badge><Badge size="compact" dir="auto">العربية</Badge>
    </div>
    <SectionTabs aria-label="Example sections">
      {['Movies', 'TV Shows'].map(label => <SectionTab key={label} type="button" active={tab === label}
        aria-pressed={tab === label} onClick={() => setTab(label)}>{label}</SectionTab>)}
    </SectionTabs>
    <SearchField onClear={() => setQuery('')}><Search size={16} /><Input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search example" aria-label="Search example" /></SearchField>
    <FormField label="Quality"><Select aria-label="Example quality" defaultValue="any"><option value="any">Any quality</option><option value="1080">1080p</option></Select></FormField>
    <WorkspaceSelectionBar selectedCount={selected} allSelected={selected === 3} label="Select example results"
      onToggleAll={checked => setSelected(checked ? 3 : 0)} onSelectAll={() => setSelected(3)} onClear={() => setSelected(0)}>
      <Button size="compact" type="button">Add to list</Button>
    </WorkspaceSelectionBar>
    <Pagination page={page} totalPages={3} total={9} pageStart={(page - 1) * 3} pageEnd={page * 3} onPageChange={setPage} ariaLabel="Example pagination" />
    <WorkspaceEmptyState size="compact" title="No matching titles" description="Clear the filters to see all titles."
      actions={<Button type="button" onClick={() => setQuery('')}>Clear filters</Button>} />
    <Button type="button" onClick={() => setDialog(true)}>Open example dialog</Button>
    <span role="status">Example saves: {saved}</span>
    {dialog && <div className="modal-backdrop" onClick={() => setDialog(false)}>
      <DialogShell as="form" role="dialog" aria-modal="true" aria-label="Example dialog" title="Edit example"
        onClick={event => event.stopPropagation()} onSubmit={event => { event.preventDefault(); setSaved(saved + 1); setDialog(false); }}
        headerActions={<Button size="icon" type="button" aria-label="Close example" onClick={() => setDialog(false)}><X size={18} /></Button>}>
        <FormField label="Title"><Input aria-label="Example title" defaultValue="Cinema Paradiso" required /></FormField>
        <DialogActions><Button type="button" onClick={() => setDialog(false)}>Cancel</Button><Button type="submit" variant="primary">Save example</Button></DialogActions>
      </DialogShell>
    </div>}
  </div>;
}
