// Shared sticky presentation for catalog navigation and controls.
export default function WorkspaceChrome({ navigation, children }) {
  return <div className="workspace-chrome">
    {navigation}
    {children}
  </div>;
}
