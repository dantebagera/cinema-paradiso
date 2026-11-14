import QtQuick
import QtQuick.Controls.Basic

ScrollView {
    id: view
    property alias verticalBar: verticalBar
    clip: true
    rightPadding: 10
    contentWidth: availableWidth
    function ensureItemVisible(target) {
        const flick = contentItem
        if (!target || !flick || !flick.contentItem) return
        const top = target.mapToItem(flick.contentItem, 0, 0).y
        let position = flick.contentY
        if (top < position) position = top
        else if (top + target.height > position + flick.height)
            position = top + target.height - flick.height
        flick.contentY = Math.max(0, Math.min(position, Math.max(0, flick.contentHeight - flick.height)))
    }
    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
    ScrollBar.vertical: CpRevealScrollBar {
        id: verticalBar
        parent: view
        anchors.right: parent.right
        y: view.topPadding
        height: view.availableHeight
        viewport: view
        flickable: view.contentItem
    }
}
