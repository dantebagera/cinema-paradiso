export function centeredWorkspaceScroll(card, workspace, stickyHeight = 0) {
  const availableHeight = workspace.height - stickyHeight;
  return Math.max(0, workspace.scrollTop + card.top - workspace.top - stickyHeight - Math.max(0, (availableHeight - card.height) / 2));
}

const pendingRestorations = new WeakMap();

export function restoreWorkspaceScroll(top, workspace = document.querySelector('.workspace')) {
  if (!workspace) return;
  pendingRestorations.get(workspace)?.();
  workspace.dataset.restoringCard = 'true';
  let secondFrame;
  const cancel = () => {
    cancelAnimationFrame(firstFrame);
    cancelAnimationFrame(secondFrame);
    if (pendingRestorations.get(workspace) !== cancel) return;
    pendingRestorations.delete(workspace);
    delete workspace.dataset.restoringCard;
  };
  const firstFrame = requestAnimationFrame(() => { secondFrame = requestAnimationFrame(() => {
    workspace.scrollTo({ top: top || 0, behavior: 'instant' });
    cancel();
  }); });
  pendingRestorations.set(workspace, cancel);
  return cancel;
}
