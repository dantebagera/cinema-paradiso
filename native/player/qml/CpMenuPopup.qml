import QtQuick
import QtQuick.Controls.Basic

// One interaction owner for ordinary menus. Resume and Up next are separate.
Popup {
    id: menu
    readonly property bool dismissalGuardActive: dismissalGuard.running
    property bool releasePending: false
    Timer { id: dismissalGuard; interval: Qt.styleHints.mouseDoubleClickInterval }
    // Qt emits overlay release before applying CloseOnReleaseOutside. Arm only
    // when that same release closes this popup, before a second press can arrive.
    Overlay.onReleased: {
        menu.releasePending = menu.visible
        Qt.callLater(() => menu.releasePending = false)
    }
    Connections {
        target: menu
        function onClosed() {
            if (menu.releasePending) {
                menu.releasePending = false
                dismissalGuard.restart()
            }
        }
    }
    popupType: Popup.Item
    modal: true
    dim: false
    focus: true
    padding: 0
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnReleaseOutside
    // Synchronous closure keeps replacement-menu callbacks in their own state.
    enter: null
    exit: null
}
