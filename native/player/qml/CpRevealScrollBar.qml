import QtQuick
import QtQuick.Controls.Basic

ScrollBar {
    id: bar
    property Item viewport: null
    property Item flickable: viewport
    readonly property bool focusWithin: viewport && viewport.Window.window
                                        ? containsFocus(viewport.Window.window.activeFocusItem) : false
    readonly property bool revealed: viewportHover.hovered || focusWithin || hovered || pressed || activity.running
    function containsFocus(item) {
        for (let candidate = item; candidate; candidate = candidate.parent)
            if (candidate === viewport) return true
        return false
    }
    function revealActivity() { activity.restart() }
    orientation: Qt.Vertical
    policy: ScrollBar.AsNeeded
    visible: size < 1 && size > 0
    implicitWidth: 8
    leftPadding: 3
    rightPadding: 3
    topPadding: 0
    bottomPadding: 0
    minimumSize: 0.04
    hoverEnabled: true
    contentItem: Rectangle {
        implicitWidth: 2
        radius: 1
        color: PlayerTheme.projectorGold
        opacity: bar.hovered || bar.pressed ? 1 : bar.revealed ? 0.72 : 0
        Behavior on opacity { NumberAnimation { duration: 120 } }
    }
    background: Item { }
    HoverHandler { id: viewportHover; parent: bar.viewport }
    Timer { id: activity; interval: 900 }
    Connections {
        target: bar.flickable
        ignoreUnknownSignals: true
        function onContentYChanged() { bar.revealActivity() }
        function onMovingChanged() { if (bar.flickable.moving) bar.revealActivity() }
    }
    onPressedChanged: if (pressed) revealActivity()
}
