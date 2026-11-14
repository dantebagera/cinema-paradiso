// Keep the page's existing request capacity while letting useful batches finish
// independently. All pending identities still receive the same full details.
export async function enrichTVCardBatches(ids, priorityIds, loadBatch, onBatch, signal) {
  const pending = [...new Set(ids)];
  const priority = new Set(priorityIds);
  const groups = [pending.filter(id => priority.has(id)), pending.filter(id => !priority.has(id))];
  const batches = groups.flatMap(group => {
    const result = [];
    for (let start = 0; start < group.length; start += 20) result.push(group.slice(start, start + 20));
    return result;
  });
  let next = 0;
  async function worker() {
    while (!signal.aborted && next < batches.length) {
      const batch = batches[next++];
      try {
        const result = await loadBatch(batch);
        if (!signal.aborted) onBatch(result);
      } catch {
        // Enrichment is best effort; one failed batch must not block the rest.
      }
    }
  }
  await Promise.all(Array.from({ length: Math.min(Math.ceil(pending.length / 20), batches.length) }, worker));
}
