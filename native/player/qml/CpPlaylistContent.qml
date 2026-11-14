import QtQuick
import QtQuick.Controls.Basic

// Presentation only. Every row retains its authoritative, flat queue index.
Column {
    id: playlist
    property var items: []
    property int currentIndex: -1
    property string mediaType: "movie"
    property bool switching: false
    property bool resumeDecisionPending: false
    property string expandedSection: ""
    readonly property bool television: mediaType === "tv"
    readonly property var groups: {
        let result = []
        items.forEach((item, index) => {
            const label = typeof item.section === "string" ? item.section.trim() : ""
            let group = television ? result.find(row => row.section === label) : result[result.length - 1]
            if (!group || group.section !== label) {
                group = {section: label, indexes: []}
                result.push(group)
            }
            group.indexes.push(index)
        })
        return result
    }
    signal itemSelected(int queueIndex)
    signal ensureVisibleRequested(Item target)
    spacing: 6

    function settleLayout() {
        for (let g = 0; g < sections.count; ++g) sections.itemAt(g).forceLayout()
        forceLayout()
    }

    function sectionFor(index) {
        const item = items[index]
        return item && typeof item.section === "string" ? item.section.trim() : ""
    }
    function playingButton() {
        for (let g = 0; g < sections.count; ++g) {
            const group = sections.itemAt(g)
            for (let r = 0; r < group.rows.count; ++r) {
                const button = group.rows.itemAt(r)
                if (button.queueIndex === currentIndex) return button
            }
        }
        return null
    }
    function resetForOpening() {
        expandedSection = currentIndex >= 0 && currentIndex < items.length ? sectionFor(currentIndex) : "\u0000"
        Qt.callLater(() => {
            playlist.settleLayout()
            const button = playingButton()
            if (button && button.visible) ensureVisibleRequested(button)
        })
    }
    onCurrentIndexChanged: resetForOpening()
    onItemsChanged: resetForOpening()
    onMediaTypeChanged: resetForOpening()

    Repeater {
        id: sections
        model: playlist.groups
        delegate: Column {
            id: section
            required property var modelData
            property alias rows: episodes
            width: playlist.width
            spacing: 6
            CpButton {
                id: header
                objectName: "seasonHeader" + section.modelData.indexes[0]
                visible: playlist.television
                width: parent.width
                text: (expanded ? "▾  " : "▸  ") + (section.modelData.section || "Episodes")
                property bool expanded: playlist.expandedSection === section.modelData.section
                Accessible.name: section.modelData.section || "Episodes"
                Accessible.role: Accessible.Button
                Accessible.description: expanded ? "Expanded" : "Collapsed"
                Accessible.checkable: true
                Accessible.checked: expanded
                contentItem: Text {
                    text: header.text
                    color: PlayerTheme.projectorGoldBright
                    font.pixelSize: 11
                    elide: Text.ElideRight
                    verticalAlignment: Text.AlignVCenter
                }
                onClicked: {
                    playlist.expandedSection = expanded ? "\u0000" : section.modelData.section
                    Qt.callLater(() => { playlist.settleLayout(); playlist.ensureVisibleRequested(header) })
                }
            }
            Text {
                visible: !playlist.television
                width: parent.width
                text: section.modelData.section || "MOVIES"
                color: PlayerTheme.projectorGoldBright
                font.pixelSize: 11
                topPadding: 10
                bottomPadding: 4
                elide: Text.ElideRight
            }
            Repeater {
                id: episodes
                model: section.modelData.indexes
                delegate: CpButton {
                    id: episode
                    required property int modelData
                    readonly property int queueIndex: modelData
                    readonly property var entry: playlist.items[queueIndex]
                    objectName: "episode" + queueIndex
                    width: section.width
                    visible: !playlist.television || playlist.expandedSection === section.modelData.section
                    highlighted: queueIndex === playlist.currentIndex
                    enabled: !playlist.switching && !playlist.resumeDecisionPending
                    text: (highlighted ? "▶  " : "") + entry.title
                    contentItem: Text {
                        text: episode.text + (episode.entry.available ? "" : "\n" + (episode.entry.reason || ""))
                        color: episode.entry.available ? PlayerTheme.textSoft : PlayerTheme.textMuted
                        font.pixelSize: 13
                        wrapMode: Text.Wrap
                    }
                    onClicked: playlist.itemSelected(queueIndex)
                }
            }
        }
    }
}
