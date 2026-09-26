export function centeredWorkspaceScroll(card, workspace) {
  return Math.max(0, workspace.scrollTop + card.top - workspace.top - (workspace.height - card.height) / 2);
}

export function restoreWorkspaceScroll(top) {
  const workspace = document.querySelector('.workspace');
  if (!workspace) return;
  workspace.dataset.restoringCard = 'true';
  requestAnimationFrame(() => requestAnimationFrame(() => {
    workspace.scrollTo({ top: top || 0, behavior: 'instant' });
    delete workspace.dataset.restoringCard;
  }));
}
