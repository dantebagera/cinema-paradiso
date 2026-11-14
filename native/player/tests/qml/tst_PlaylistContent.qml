import QtQuick
import QtQuick.Controls
import QtTest
import CinemaParadiso.Player 1.0

TestCase {
    name: "PlaylistContent"
    width: 460
    height: 720
    visible: true
    when: windowShown
    Component { id: playlistFactory; CpPlaylistContent { width: 400 } }
    SignalSpy { id: selection; signalName: "itemSelected" }
    property var playlist
    function fixture() {
        let rows = []
        for (let season = 1; season <= 6; ++season)
            for (let episode = 1; episode <= 20; ++episode)
                rows.push({title: "S0" + season + "E" + episode + " · عنوان طويل", section: "Season " + season,
                           available: episode !== 19, reason: episode === 19 ? "Missing locally" : ""})
        return rows
    }
    function init() {
        playlist = createTemporaryObject(playlistFactory, this, {items: fixture(), currentIndex: 22, mediaType: "tv"})
        selection.target = playlist
        selection.clear()
        playlist.resetForOpening()
        wait(30)
    }
    function test_currentSeasonOnOpen() {
        verify(!findChild(playlist, "episode0").visible, "Season 1 must start collapsed")
        verify(findChild(playlist, "episode22").visible)
        verify(findChild(playlist, "episode22").highlighted)
        verify(!findChild(playlist, "episode119").visible)
    }
    function test_oneSeasonAtATime() {
        mouseClick(findChild(playlist, "seasonHeader100"))
        verify(findChild(playlist, "episode119").visible)
        verify(!findChild(playlist, "episode22").visible)
        compare(selection.count, 0)
    }
    function test_originalQueueIndexForS06E20() {
        mouseClick(findChild(playlist, "seasonHeader100"))
        wait(30) // Wait for the real Column layout after the accordion collapses.
        let target = findChild(playlist, "episode119")
        playlist.y = 100 - target.mapToItem(playlist, 0, 0).y
        mouseClick(target)
        compare(selection.count, 1)
        compare(selection.signalArguments[0][0], 119)
    }
    function test_moviesRemainFlat() {
        playlist.mediaType = "movie"
        wait(20)
        verify(findChild(playlist, "episode0").visible)
        verify(findChild(playlist, "episode119").visible)
    }
    function test_reopenRestoresPlayingSeason() {
        mouseClick(findChild(playlist, "seasonHeader100"))
        playlist.resetForOpening()
        verify(findChild(playlist, "episode22").visible)
        verify(!findChild(playlist, "episode119").visible)
    }
    function test_unavailableAndMalformedPreserveIndexes() {
        playlist.items = [ {title: "Special", section: "Specials", available: true},
                           {title: "Bad section", section: "", available: false, reason: "Missing locally"} ]
        playlist.currentIndex = 1
        playlist.resetForOpening()
        wait(30)
        let row = findChild(playlist, "episode1")
        verify(row.visible)
        verify(row.contentItem.text.indexOf("Missing locally") >= 0)
        mouseClick(row)
        compare(selection.signalArguments[0][0], 1)
    }
    Component {
        id: scrollFactory
        CpScrollView {
            id: scroll
            width: 400; height: 400
            CpPlaylistContent {
                id: content
                width: scroll.availableWidth
                mediaType: "tv"
                onEnsureVisibleRequested: target => scroll.ensureItemVisible(target)
            }
        }
    }
    function test_playingEpisodeActuallyInsideViewport() {
        let view = createTemporaryObject(scrollFactory, this)
        let content = view.contentChildren[0]
        content.items = fixture()
        content.currentIndex = 22
        content.resetForOpening()
        wait(100)
        let row = findChild(content, "episode22")
        let top = row.mapToItem(view, 0, 0).y
        verify(top >= 0 && top + row.height <= view.height,
               "Playing row outside viewport: " + top + ", scroll=" + view.contentItem.contentY)
    }
}
