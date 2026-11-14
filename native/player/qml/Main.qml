import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import CinemaParadiso.Player

ApplicationWindow {
    id: root
    width: Math.min(1280, Screen.desktopAvailableWidth * 0.92)
    height: Math.min(720, Screen.desktopAvailableHeight * 0.90)
    minimumWidth: Math.min(860, Screen.desktopAvailableWidth * 0.82)
    minimumHeight: Math.min(520, Screen.desktopAvailableHeight * 0.72)
    x: Math.max(0, (Screen.desktopAvailableWidth - width) / 2)
    y: Math.max(0, (Screen.desktopAvailableHeight - height) / 2)
    visible: true
    color: PlayerTheme.archiveBlack
    readonly property bool dismissalGuardActive: playerSidePanel.dismissalGuardActive || trackPanel.dismissalGuardActive
                                                || subtitleSearchPanel.dismissalGuardActive || statisticsPanel.dismissalGuardActive
                                                || speedPanel.dismissalGuardActive
    readonly property bool blocksWindowGestures: dismissalGuardActive || sidePanelMode.length > 0
                                                || audioPanelOpen || subtitlePanelOpen || chapterPanelOpen
                                                || subtitleSearchOpen || statisticsOpen || speedPanel.visible
    flags: Qt.Window | Qt.FramelessWindowHint
    title: playerBridge.title.length > 0
           ? playerBridge.title + " — Cinema Paradiso"
           : "Cinema Paradiso Player"

    property bool controlsVisible: true
    property bool audioPanelOpen: false
    property bool subtitlePanelOpen: false
    property bool chapterPanelOpen: false
    property bool subtitleSearchOpen: false
    property bool statisticsOpen: false
    property var playbackStatistics: ({})
    property string sidePanelMode: ""
    property bool placementRestored: false
    property bool alwaysOnTop: Boolean(root.flags & Qt.WindowStaysOnTopHint)
    property int upNextSeconds: 0
    property var queueItems: playerBridge.queue.items || []
    readonly property bool hasPlaylist: queueItems.length > 1
    property int playingQueueIndex: -1
    property string lastQueueError: ""
    onHasPlaylistChanged: if (!hasPlaylist && sidePanelMode === "playlist") sidePanelMode = ""
    property int queueIndex: playerBridge.queue.current_index === undefined ? -1 : playerBridge.queue.current_index
    property string repeatStatus: "Off"
    onSidePanelModeChanged: {
        if (sideScroll.contentItem && sideScroll.contentItem.contentY !== undefined)
            sideScroll.contentItem.contentY = 0
        if (sidePanelMode === "playlist") playlistContent.resetForOpening()
    }
    property var settingsActions: [
        { section: "PLAYBACK", title: "Autoplay next file", action: "autoplay", value: playerBridge.autoplay ? "On" : "Off" },
        { section: "PLAYBACK", title: "Back 10 seconds", action: "seek_backward" },
        { section: "PLAYBACK", title: "Forward 10 seconds", action: "seek_forward" },
        { section: "PLAYBACK", title: "Back 1 minute", action: "seek_backward_long" },
        { section: "PLAYBACK", title: "Forward 1 minute", action: "seek_forward_long" },
        { section: "PLAYBACK", title: "Chapters", action: "chapters" },
        { section: "PLAYBACK", title: "A–B repeat", action: "ab_repeat", value: root.repeatStatus },
        { section: "WINDOW & PICTURE", title: "Always on top", action: "always_on_top", value: root.alwaysOnTop ? "On" : "Off" },
        { section: "WINDOW & PICTURE", title: "Cycle aspect ratio", action: "aspect_ratio" },
        { section: "WINDOW & PICTURE", title: "Cycle crop", action: "crop" },
        { section: "WINDOW & PICTURE", title: "Rotate 90°", action: "rotate" },
        { section: "WINDOW & PICTURE", title: "Zoom in", action: "zoom_in" },
        { section: "WINDOW & PICTURE", title: "Zoom out", action: "zoom_out" },
        { section: "WINDOW & PICTURE", title: "Move picture left", action: "pan_left" },
        { section: "WINDOW & PICTURE", title: "Move picture right", action: "pan_right" },
        { section: "WINDOW & PICTURE", title: "Move picture up", action: "pan_up" },
        { section: "WINDOW & PICTURE", title: "Move picture down", action: "pan_down" },
        { section: "WINDOW & PICTURE", title: "Reset picture adjustments", action: "reset_picture" },
        { section: "AUDIO & SUBTITLES", title: "Audio earlier · 0.1 s", action: "audio_delay_down" },
        { section: "AUDIO & SUBTITLES", title: "Audio later · 0.1 s", action: "audio_delay_up" },
        { section: "AUDIO & SUBTITLES", title: "Subtitles earlier · 0.1 s", action: "subtitle_delay_down" },
        { section: "AUDIO & SUBTITLES", title: "Subtitles later · 0.1 s", action: "subtitle_delay_up" },
        { section: "AUDIO & SUBTITLES", title: "Search subtitles", action: "subtitle_search" },
        { section: "ADVANCED", title: "Save screenshot", action: "screenshot" },
        { section: "ADVANCED", title: "Advance one frame", action: "frame_advance" },
        { section: "ADVANCED", title: "Playback statistics", action: "statistics" },
        { section: "HELP", title: "Keyboard shortcuts", action: "shortcuts" }
    ]
    property string toastText: ""
    property bool seeking: timeline.scrubbing || timeline.previewActive

    component CpIconButton: AbstractButton {
        id: iconControl
        required property url iconSource
        required property string label
        Accessible.name: label
        property bool selected: false
        implicitWidth: 42
        implicitHeight: 42
        hoverEnabled: true
        focusPolicy: Qt.StrongFocus
        scale: down ? 0.92 : 1

        Behavior on scale {
            NumberAnimation { duration: 90; easing.type: Easing.OutCubic }
        }

        contentItem: Item {
            Image {
                anchors.centerIn: parent
                width: 28
                height: 28
                source: iconControl.iconSource
                fillMode: Image.PreserveAspectFit
                sourceSize.width: 56
                sourceSize.height: 56
                opacity: !iconControl.enabled
                         ? PlayerTheme.playerGoldDisabledOpacity
                         : iconControl.hovered || iconControl.activeFocus || iconControl.selected
                           ? PlayerTheme.playerGoldActiveOpacity
                           : PlayerTheme.playerGoldRestOpacity
                scale: iconControl.hovered || iconControl.activeFocus ? 1.06 : 1

                Behavior on scale {
                    NumberAnimation { duration: 120; easing.type: Easing.OutCubic }
                }
                Behavior on opacity { NumberAnimation { duration: 120 } }
            }
        }

        background: Rectangle {
            color: "transparent"
            border.width: 0
        }

        ToolTip.visible: iconControl.hovered
        ToolTip.delay: 450
        ToolTip.text: iconControl.label
    }

    component CpAudioTracksButton: AbstractButton {
        id: audioTracksButton
        required property int trackCount
        property bool selected: false
        implicitWidth: 42
        implicitHeight: 42
        hoverEnabled: true
        focusPolicy: Qt.StrongFocus
        scale: down ? 0.92 : 1

        Behavior on scale {
            NumberAnimation { duration: 90; easing.type: Easing.OutCubic }
        }

        contentItem: Item {
            Image {
                anchors.centerIn: parent
                width: 28
                height: 28
                source: "qrc:/icons/audio-language-tracks.svg"
                fillMode: Image.PreserveAspectFit
                sourceSize.width: 56
                sourceSize.height: 56
                opacity: audioTracksButton.hovered || audioTracksButton.activeFocus
                         || audioTracksButton.selected
                         ? PlayerTheme.playerGoldActiveOpacity
                         : PlayerTheme.playerGoldRestOpacity
            }
            Text {
                x: 22
                y: 15
                width: 12
                height: 12
                text: audioTracksButton.trackCount > 9 ? "9+" : String(audioTracksButton.trackCount)
                color: "#0B0A08"
                font.pixelSize: audioTracksButton.trackCount > 9 ? 7 : 10
                font.weight: Font.DemiBold
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
        }

        background: Rectangle {
            color: "transparent"
            border.width: 0
        }

        ToolTip.visible: audioTracksButton.hovered
        ToolTip.delay: 450
        ToolTip.text: audioTracksButton.trackCount + " audio tracks"
    }

    function showControls() {
        controlsVisible = true
        hideControls.restart()
    }

    function adjustVolumeFromWheel(delta) {
        if (!delta)
            return
        const volume = Math.max(0, Math.min(100, mpv.volume + (delta > 0 ? 5 : -5)))
        mpv.setVolume(volume)
        toastText = "Volume " + Math.round(volume) + "%"
        toastTimer.restart()
        showControls()
    }

    function isVideoArea(point) {
        return !(topBar.visible && point.y < topBar.height)
                && !(bottomBar.visible && point.y >= bottomBar.y)
    }

    function colorWithOpacity(color, opacity) {
        return Qt.rgba(color.r, color.g, color.b, opacity)
    }

    function closeMenus() {
        const hadMenu = audioPanelOpen || subtitlePanelOpen || chapterPanelOpen || subtitleSearchOpen
                        || statisticsOpen || speedPanel.visible || sidePanelMode.length > 0
        sidePanelMode = ""
        audioPanelOpen = false
        subtitlePanelOpen = false
        chapterPanelOpen = false
        subtitleSearchOpen = false
        statisticsOpen = false
        speedPanel.close()
        if (hadMenu) showControls()
        return hadMenu
    }

    function closeOverlays() {
        const hadCountdown = upNextSeconds > 0
        upNextSeconds = 0
        return closeMenus() || hadCountdown
    }

    function ensureSideItemVisible(target) {
        sideColumn.forceLayout()
        sideScroll.ensureItemVisible(target)
    }

    function showSubtitleSearch() {
        sidePanelMode = ""
        upNextSeconds = 0
        subtitleSearchOpen = true
        audioPanelOpen = false
        subtitlePanelOpen = false
        chapterPanelOpen = false
        speedPanel.close()
        playerBridge.requestSubtitleSearch()
        showControls()
    }

    function toggleFullscreen() {
        visibility = visibility === Window.FullScreen ? Window.Windowed : Window.FullScreen
        showControls()
    }

    function setAlwaysOnTop(enabled) {
        const current = Boolean(root.flags & Qt.WindowStaysOnTopHint)
        if (current === enabled)
            return
        if (enabled)
            root.flags = root.flags | Qt.WindowStaysOnTopHint
        else
            root.flags = root.flags & ~Qt.WindowStaysOnTopHint
        playerBridge.reportWindowState(root.x, root.y, root.width, root.height, Screen.name,
                                      root.visibility === Window.Maximized, enabled)
    }

    function openSidePanel(mode) {
        if (mode === "playlist" && !hasPlaylist) return
        const alreadyOpen = sidePanelMode === mode
        closeOverlays()
        sidePanelMode = alreadyOpen ? "" : mode
        showControls()
    }

    function neighborLabel(offset) {
        const row = queueItems[queueIndex + offset]
        return (offset < 0 ? "Previous" : "Next") + (row ? ": " + row.title + (row.available ? "" : " — " + row.reason) : " file")
    }

    function selectFile(index, automatic) {
        upNextSeconds = 0
        if (index < 0 || index >= queueItems.length) return
        if (!queueItems[index].available) {
            toastText = queueItems[index].reason
            toastTimer.restart()
            sidePanelMode = hasPlaylist ? "playlist" : ""
        } else {
            closeOverlays()
            playerBridge.selectQueueItem(index, automatic)
        }
        showControls()
    }

    function runPlayerAction(action) {
        switch (action) {
        case "autoplay": playerBridge.setAutoplay(!playerBridge.autoplay); break
        case "always_on_top": root.setAlwaysOnTop(!root.alwaysOnTop); break
        case "seek_backward": mpv.seekRelative(-10); break
        case "seek_forward": mpv.seekRelative(10); break
        case "seek_backward_long": mpv.seekRelative(-60); break
        case "seek_forward_long": mpv.seekRelative(60); break
        case "chapters": closeOverlays(); chapterPanelOpen = true; break
        case "ab_repeat": repeatStatus = mpv.cycleABRepeat(); toastText = repeatStatus; break
        case "aspect_ratio": mpv.cycleAspectRatio(); toastText = "Aspect ratio changed"; break
        case "crop": mpv.cycleCrop(); toastText = "Crop changed"; break
        case "rotate": mpv.rotateVideo(); break
        case "zoom_in": mpv.adjustZoom(0.1); break
        case "zoom_out": mpv.adjustZoom(-0.1); break
        case "pan_left": mpv.adjustPan(-0.05, 0); break
        case "pan_right": mpv.adjustPan(0.05, 0); break
        case "pan_up": mpv.adjustPan(0, -0.05); break
        case "pan_down": mpv.adjustPan(0, 0.05); break
        case "reset_picture": mpv.resetPicture(); toastText = "Picture adjustments reset"; break
        case "audio_delay_down": mpv.adjustAudioDelay(-0.1); toastText = "Audio −0.1 s"; break
        case "audio_delay_up": mpv.adjustAudioDelay(0.1); toastText = "Audio +0.1 s"; break
        case "subtitle_delay_down": mpv.adjustSubtitleDelay(-0.1); toastText = "Subtitles −0.1 s"; break
        case "subtitle_delay_up": mpv.adjustSubtitleDelay(0.1); toastText = "Subtitles +0.1 s"; break
        case "subtitle_search": closeOverlays(); showSubtitleSearch(); break
        case "screenshot": toastText = mpv.captureScreenshot(); break
        case "frame_advance": mpv.frameAdvance(); break
        case "statistics": closeOverlays(); playbackStatistics = mpv.playbackStatistics(); statisticsOpen = true; break
        case "shortcuts": sidePanelMode = "shortcuts"; break
        }
        if (toastText.length > 0) toastTimer.restart()
        showControls()
    }

    function restoreWindowState() {
        const state = playerBridge.windowState
        if (!state || !state.width || !state.positioned)
            return
        root.width = state.width
        root.height = state.height
        root.x = state.x
        root.y = state.y
        root.setAlwaysOnTop(Boolean(state.always_on_top))
        if (state.maximized)
            root.visibility = Window.Maximized
    }

    function activatePlayerWindow() {
        root.requestActivate()
        mpv.forceActiveFocus()
    }

    Component.onCompleted: Qt.callLater(root.activatePlayerWindow)
    onActiveChanged: {
        if (active)
            mpv.forceActiveFocus()
    }

    function formatTime(seconds) {
        if (!isFinite(seconds) || seconds < 0)
            return "0:00"
        const total = Math.floor(seconds)
        const hours = Math.floor(total / 3600)
        const minutes = Math.floor((total % 3600) / 60)
        const secs = total % 60
        return hours > 0
                ? hours + ":" + String(minutes).padStart(2, "0") + ":" + String(secs).padStart(2, "0")
                : minutes + ":" + String(secs).padStart(2, "0")
    }

    function trackLabel(track) {
        const language = track.language && track.language !== "und" ? track.language.toUpperCase() : "Unknown"
        const detail = [track.title, track.codec ? track.codec.toUpperCase() : "",
                        track.channels].filter(Boolean).join(" — ")
        const flags = [track.default ? "Default" : "", track.forced ? "Forced" : "",
                       track.hearing_impaired ? "SDH" : ""].filter(Boolean).join(" · ")
        return language + (detail ? " — " + detail : "") + (flags ? " · " + flags : "")
    }

    onClosing: function(close) {
        playerBridge.reportWindowState(
            root.x, root.y, root.width, root.height, Screen.name,
            root.visibility === Window.Maximized,
            Boolean(root.flags & Qt.WindowStaysOnTopHint)
        )
        playerBridge.requestClose()
    }

    Connections {
        target: playerBridge
        function onPreferencesChanged() {
            if (!root.placementRestored) {
                root.restoreWindowState()
                root.placementRestored = true
                Qt.callLater(root.activatePlayerWindow)
            }
        }
        function onNaturalEndReached() {
            root.showControls()
            if (playerBridge.queue.autoplay_blocked_reason) {
                root.toastText = playerBridge.queue.autoplay_blocked_reason
                root.sidePanelMode = root.hasPlaylist ? "playlist" : ""
                toastTimer.restart()
                return
            }
            const next = root.queueItems[root.queueIndex + 1]
            if (!next) return
            if (!next.available) {
                root.toastText = next.reason
                toastTimer.restart()
                root.sidePanelMode = root.hasPlaylist ? "playlist" : ""
            } else if (playerBridge.autoplay) {
                root.closeOverlays()
                root.upNextSeconds = 5
            }
        }
        function onMediaChanged() { root.upNextSeconds = 0; root.repeatStatus = "Off" }
        function onQueueChanged() {
            if (!playerBridge.autoplay) root.upNextSeconds = 0
            if (!playerBridge.switching && root.playingQueueIndex !== root.queueIndex) {
                root.playingQueueIndex = root.queueIndex
                if (root.sidePanelMode === "playlist") playlistContent.resetForOpening()
            }
            const error = playerBridge.queueError
            if (error.length > 0) {
                root.showControls()
                if (!root.hasPlaylist && error !== root.lastQueueError) {
                    root.toastText = error
                    toastTimer.restart()
                }
            }
            root.lastQueueError = error
        }
    }

    Timer {
        interval: 1000
        repeat: true
        running: root.upNextSeconds > 0
        onTriggered: {
            root.upNextSeconds -= 1
            if (root.upNextSeconds === 0) root.selectFile(root.queueIndex + 1, true)
        }
    }

    Timer {
        id: hideControls
        interval: PlayerTheme.controlsHideMs
        running: true
        repeat: false
        onTriggered: {
            if (!mpv.paused && !root.seeking && !audioPanelOpen && !subtitlePanelOpen
                    && !chapterPanelOpen && !subtitleSearchOpen
                    && !statisticsOpen && !speedPanel.opened
                    && root.sidePanelMode.length === 0 && root.upNextSeconds === 0
                    && !playerBridge.resumeDecisionPending)
                controlsVisible = false
        }
    }

    Timer {
        id: toastTimer
        interval: 1800
        onTriggered: toastText = ""
    }
    Timer {
        interval: 1000
        running: statisticsOpen
        repeat: true
        triggeredOnStart: true
        onTriggered: playbackStatistics = mpv.playbackStatistics()
    }

    Shortcut { enabled: !playerBridge.resumeDecisionPending; sequence: playerBridge.shortcuts.play_pause || "Space"; onActivated: { mpv.togglePause(); root.showControls() } }
    Shortcut { enabled: !playerBridge.resumeDecisionPending; sequence: playerBridge.shortcuts.seek_backward || "Left"; onActivated: { mpv.seekRelative(-10); root.showControls() } }
    Shortcut { enabled: !playerBridge.resumeDecisionPending; sequence: playerBridge.shortcuts.seek_forward || "Right"; onActivated: { mpv.seekRelative(10); root.showControls() } }
    Shortcut { enabled: !playerBridge.resumeDecisionPending; sequence: playerBridge.shortcuts.seek_backward_long || "Shift+Left"; onActivated: { mpv.seekRelative(-60); root.showControls() } }
    Shortcut { enabled: !playerBridge.resumeDecisionPending; sequence: playerBridge.shortcuts.seek_forward_long || "Shift+Right"; onActivated: { mpv.seekRelative(60); root.showControls() } }
    Shortcut { sequence: playerBridge.shortcuts.volume_up || "Up"; onActivated: { mpv.setVolume(mpv.volume + 5); root.showControls() } }
    Shortcut { sequence: playerBridge.shortcuts.volume_down || "Down"; onActivated: { mpv.setVolume(mpv.volume - 5); root.showControls() } }
    Shortcut { sequence: playerBridge.shortcuts.mute || "M"; onActivated: { mpv.toggleMute(); root.showControls() } }
    Shortcut { sequence: playerBridge.shortcuts.fullscreen || "F"; onActivated: root.toggleFullscreen() }
    Shortcut { enabled: !playerBridge.resumeDecisionPending && !subtitleSearchOpen; sequence: "Enter"; onActivated: root.toggleFullscreen() }
    Shortcut { enabled: playerBridge.resumeDecisionPending; sequence: "Return"; onActivated: playerBridge.chooseResume() }
    Shortcut {
        enabled: subtitleSearchOpen && playerBridge.subtitleResults.length > 0
        sequence: "Return"
        onActivated: playerBridge.requestSubtitleDownload(
            playerBridge.subtitleResults[0].result_id
        )
    }
    Shortcut { enabled: playerBridge.resumeDecisionPending; sequence: "R"; onActivated: playerBridge.chooseRestart() }
    Shortcut {
        sequence: "Escape"
        onActivated: {
            if (!root.closeOverlays() && root.visibility === Window.FullScreen)
                root.visibility = Window.Windowed
        }
    }
    Shortcut {
        sequence: playerBridge.shortcuts.audio_tracks || "A"
        onActivated: {
            sidePanelMode = ""
            upNextSeconds = 0
            audioPanelOpen = !audioPanelOpen
            subtitlePanelOpen = false
            chapterPanelOpen = false
            subtitleSearchOpen = false
            speedPanel.close()
            root.showControls()
        }
    }
    Shortcut {
        sequence: playerBridge.shortcuts.subtitle_tracks || "S"
        onActivated: {
            sidePanelMode = ""
            upNextSeconds = 0
            subtitlePanelOpen = !subtitlePanelOpen
            audioPanelOpen = false
            chapterPanelOpen = false
            subtitleSearchOpen = false
            speedPanel.close()
            root.showControls()
        }
    }
    Shortcut {
        sequence: playerBridge.shortcuts.subtitle_search || "D"
        onActivated: root.showSubtitleSearch()
    }
    Shortcut {
        sequence: playerBridge.shortcuts.chapters || "C"
        onActivated: {
            sidePanelMode = ""
            upNextSeconds = 0
            chapterPanelOpen = !chapterPanelOpen
            audioPanelOpen = false
            subtitlePanelOpen = false
            subtitleSearchOpen = false
            speedPanel.close()
            root.showControls()
        }
    }
    Shortcut { sequence: playerBridge.shortcuts.speed_down || "["; onActivated: { mpv.setSpeed(mpv.speed - 0.05); root.showControls() } }
    Shortcut { sequence: playerBridge.shortcuts.speed_up || "]"; onActivated: { mpv.setSpeed(mpv.speed + 0.05); root.showControls() } }
    Shortcut { sequence: playerBridge.shortcuts.subtitle_delay_down || "Z"; onActivated: { mpv.adjustSubtitleDelay(-0.1); toastText = "Subtitles −0.1 s"; toastTimer.restart(); root.showControls() } }
    Shortcut { sequence: playerBridge.shortcuts.subtitle_delay_up || "X"; onActivated: { mpv.adjustSubtitleDelay(0.1); toastText = "Subtitles +0.1 s"; toastTimer.restart(); root.showControls() } }
    Shortcut { sequence: playerBridge.shortcuts.audio_delay_down || "Ctrl+Z"; onActivated: { mpv.adjustAudioDelay(-0.1); toastText = "Audio −0.1 s"; toastTimer.restart(); root.showControls() } }
    Shortcut { sequence: playerBridge.shortcuts.audio_delay_up || "Ctrl+X"; onActivated: { mpv.adjustAudioDelay(0.1); toastText = "Audio +0.1 s"; toastTimer.restart(); root.showControls() } }
    Shortcut {
        sequence: playerBridge.shortcuts.statistics || "I"
        onActivated: {
            sidePanelMode = ""
            upNextSeconds = 0
            statisticsOpen = !statisticsOpen
            audioPanelOpen = false
            subtitlePanelOpen = false
            chapterPanelOpen = false
            subtitleSearchOpen = false
            speedPanel.close()
            playbackStatistics = mpv.playbackStatistics()
            root.showControls()
        }
    }
    Shortcut {
        sequence: playerBridge.shortcuts.screenshot || "P"
        onActivated: {
            toastText = mpv.captureScreenshot()
            toastTimer.restart()
            root.showControls()
        }
    }
    Shortcut { sequence: playerBridge.shortcuts.ab_repeat || "Ctrl+B"; onActivated: root.runPlayerAction("ab_repeat") }
    Shortcut { sequence: playerBridge.shortcuts.frame_advance || "."; onActivated: { mpv.frameAdvance(); root.showControls() } }
    Shortcut { sequence: playerBridge.shortcuts.aspect_ratio || "V"; onActivated: { mpv.cycleAspectRatio(); toastText = "Aspect ratio changed"; toastTimer.restart(); root.showControls() } }
    Shortcut { sequence: playerBridge.shortcuts.crop || "Shift+V"; onActivated: { mpv.cycleCrop(); toastText = "Video crop changed"; toastTimer.restart(); root.showControls() } }
    Shortcut { sequence: playerBridge.shortcuts.rotate || "Alt+R"; onActivated: { mpv.rotateVideo(); toastText = "Video rotated"; toastTimer.restart(); root.showControls() } }
    Shortcut { sequence: playerBridge.shortcuts.zoom_in || "Ctrl++"; onActivated: { mpv.adjustZoom(0.1); toastText = "Zoom in"; toastTimer.restart(); root.showControls() } }
    Shortcut { sequence: playerBridge.shortcuts.zoom_out || "Ctrl+-"; onActivated: { mpv.adjustZoom(-0.1); toastText = "Zoom out"; toastTimer.restart(); root.showControls() } }
    Shortcut { sequence: playerBridge.shortcuts.pan_left || "Alt+Left"; onActivated: mpv.adjustPan(-0.05, 0) }
    Shortcut { sequence: playerBridge.shortcuts.pan_right || "Alt+Right"; onActivated: mpv.adjustPan(0.05, 0) }
    Shortcut { sequence: playerBridge.shortcuts.pan_up || "Alt+Up"; onActivated: mpv.adjustPan(0, -0.05) }
    Shortcut { sequence: playerBridge.shortcuts.pan_down || "Alt+Down"; onActivated: mpv.adjustPan(0, 0.05) }
    Shortcut {
        sequence: playerBridge.shortcuts.always_on_top || "T"
        onActivated: {
            root.setAlwaysOnTop(!(root.flags & Qt.WindowStaysOnTopHint))
            toastText = (root.flags & Qt.WindowStaysOnTopHint)
                        ? "Always on top" : "Normal window"
            toastTimer.restart()
        }
    }

    Rectangle {
        anchors.fill: parent
        color: PlayerTheme.archiveBlack
    }

    Image {
        anchors.fill: parent
        anchors.margins: 48
        source: playerBridge.posterReference
        fillMode: Image.PreserveAspectFit
        opacity: mpv.status === "Loading" ? 0.18 : 0
        asynchronous: true
        cache: false
    }

    MpvItem {
        id: mpv
        objectName: "mpvItem"
        anchors.fill: parent
        focus: true
        onPausedChanged: root.showControls()
        onPlaybackEnded: root.showControls()
        onPositionChanged: {
            if (root.upNextSeconds > 0 && mpv.duration > 0 && mpv.position < mpv.duration - 0.5)
                root.upNextSeconds = 0
        }
    }

    MouseArea {
        enabled: !root.dismissalGuardActive
        anchors.fill: parent
        acceptedButtons: Qt.NoButton
        hoverEnabled: true
        cursorShape: root.visibility === Window.FullScreen && !root.controlsVisible
                     ? Qt.BlankCursor : Qt.ArrowCursor
        onPositionChanged: root.showControls()

        TapHandler {
            enabled: !root.dismissalGuardActive && !playerBridge.resumeDecisionPending
                     && root.sidePanelMode.length === 0
                     && !audioPanelOpen
                     && !subtitlePanelOpen
                     && !chapterPanelOpen
                     && !subtitleSearchOpen
                     && !statisticsOpen
                     && !speedPanel.opened
            acceptedButtons: Qt.LeftButton
            onSingleTapped: eventPoint => {
                const point = eventPoint.position
                if (root.isVideoArea(point)) {
                    mpv.togglePause()
                    root.showControls()
                }
            }
            onDoubleTapped: eventPoint => {
                if (root.isVideoArea(eventPoint.position))
                    root.toggleFullscreen()
            }
        }

        WheelHandler {
            enabled: !root.dismissalGuardActive && !playerBridge.resumeDecisionPending
                     && root.sidePanelMode.length === 0
                     && !audioPanelOpen
                     && !subtitlePanelOpen
                     && !chapterPanelOpen
                     && !subtitleSearchOpen
                     && !statisticsOpen
                     && !speedPanel.opened
            onWheel: event => root.adjustVolumeFromWheel(event.angleDelta.y)
        }
    }

    Rectangle {
        id: topBar
        enabled: !root.dismissalGuardActive
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: nowPlayingSummary.height + 40
        opacity: root.controlsVisible ? 1 : 0
        visible: opacity > 0
        color: "transparent"

        gradient: Gradient {
            GradientStop { position: 0; color: "#d9000000" }
            GradientStop { position: 1; color: "#00000000" }
        }
        Behavior on opacity { NumberAnimation { duration: 160 } }

        Row {
            id: nowPlayingSummary
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.leftMargin: 28
            anchors.topMargin: 20
            height: 156
            spacing: 14

            Item {
                id: nowPlayingPosterFrame
                width: 104
                height: nowPlayingSummary.height
                visible: playerBridge.posterReference.length > 0
                         && posterImage.status !== Image.Error
                         && posterImage.status !== Image.Null

                Image {
                    id: posterImage
                    anchors.fill: parent
                    source: playerBridge.posterReference
                    fillMode: Image.PreserveAspectFit
                    asynchronous: true
                    cache: false
                    smooth: true
                    mipmap: true
                }
            }

            Column {
                y: Math.max(0, (nowPlayingSummary.height - height) / 2)
                spacing: 4

                Text {
                    text: playerBridge.title || "Cinema Paradiso"
                    color: PlayerTheme.textStrong
                    font.pixelSize: 22
                    font.weight: Font.DemiBold
                    elide: Text.ElideRight
                    width: Math.min(
                        720,
                        root.width - 180
                        - (nowPlayingPosterFrame.visible
                           ? nowPlayingPosterFrame.width + nowPlayingSummary.spacing
                           : 0)
                    )
                }
                Text {
                    text: [playerBridge.year, mpv.paused ? "Paused" : mpv.status]
                          .filter(Boolean).join("  ·  ")
                    color: PlayerTheme.textMuted
                    font.pixelSize: 13
                }
            }
        }

    }

    Row {
        id: windowControls
        enabled: !root.dismissalGuardActive
        z: 1200
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.topMargin: 6
        anchors.rightMargin: 8
        height: windowChrome.dragHeight
        spacing: 4
        visible: opacity > 0
        opacity: root.controlsVisible ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 160 } }

        CpIconButton {
            iconSource: "qrc:/icons/window-minimize.svg"
            label: "Minimize"
            onClicked: windowChrome.minimize()
        }
        CpIconButton {
            iconSource: "qrc:/icons/window-close.svg"
            label: "Close"
            onClicked: windowChrome.closeWindow()
        }
    }

    Rectangle {
        id: bottomBar
        enabled: !root.dismissalGuardActive
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 170
        opacity: root.controlsVisible ? 1 : 0
        visible: opacity > 0
        color: "transparent"
        gradient: Gradient {
            GradientStop { position: 0; color: "#00000000" }
            GradientStop { position: 1; color: "#ed000000" }
        }
        Behavior on opacity { NumberAnimation { duration: 160 } }

        ColumnLayout {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.leftMargin: 28
            anchors.rightMargin: 28
            anchors.bottomMargin: 20
            spacing: 8

            Slider {
                id: timeline
                Layout.fillWidth: true
                Layout.preferredHeight: 28
                from: 0
                to: Math.max(1, mpv.duration)
                value: 0
                property real hoverPosition: 0
                property string hoverThumbnail: ""
                property real previewX: 0
                property bool scrubbing: timelinePointer.pressed
                property bool previewActive: false
                function positionForX(localX) {
                    const trackX = Math.max(0, Math.min(
                        availableWidth,
                        localX - leftPadding
                    ))
                    previewX = leftPadding + trackX
                    return to * trackX / Math.max(1, availableWidth)
                }
                function updateHoverPreview(localX) {
                    hoverPosition = positionForX(localX)
                    hoverThumbnail = mpv.seekThumbnail(hoverPosition)
                }
                function seekFromPointer(localX) {
                    root.showControls()
                    value = positionForX(localX)
                    updateHoverPreview(localX)
                    mpv.seekAbsolute(value)
                }
                MouseArea {
                    id: timelinePointer
                    anchors.fill: parent
                    z: 20
                    acceptedButtons: Qt.LeftButton
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onEntered: timeline.previewActive = true
                    onPressed: mouse => {
                        timeline.previewActive = true
                        timeline.seekFromPointer(mouse.x)
                    }
                    onPositionChanged: mouse => {
                        timeline.previewActive = true
                        if (pressed)
                            timeline.seekFromPointer(mouse.x)
                        else
                            timeline.updateHoverPreview(mouse.x)
                    }
                    onReleased: mouse => timeline.seekFromPointer(mouse.x)
                    onExited: {
                        timeline.previewActive = false
                        timeline.hoverThumbnail = ""
                    }
                }
                Timer {
                    interval: 120
                    running: timeline.previewActive
                    repeat: true
                    triggeredOnStart: true
                    onTriggered: timeline.updateHoverPreview(timelinePointer.mouseX)
                }
                Connections {
                    target: mpv
                    function onPositionChanged() {
                        if (!timeline.scrubbing)
                            timeline.value = mpv.position
                    }
                    function onSeekThumbnailsChanged() {
                        if (timeline.previewActive)
                            timeline.updateHoverPreview(timelinePointer.mouseX)
                    }
                }
                background: Rectangle {
                    x: parent.leftPadding
                    y: parent.topPadding + parent.availableHeight / 2 - height / 2
                    width: parent.availableWidth
                    height: 4
                    radius: 2
                    color: PlayerTheme.borderStrong
                    Rectangle {
                        width: parent.width * timeline.visualPosition
                        height: parent.height
                        radius: 2
                        color: PlayerTheme.projectorGold
                        opacity: timeline.previewActive
                                 ? PlayerTheme.playerGoldActiveOpacity
                                 : PlayerTheme.playerGoldProgressOpacity
                    }
                    Repeater {
                        model: mpv.chapters
                        delegate: Rectangle {
                            required property var modelData
                            x: Math.max(0, Math.min(parent.width - 2,
                                parent.width * Number(modelData.time || 0)
                                / Math.max(1, mpv.duration)))
                            width: 2
                            height: 10
                            anchors.verticalCenter: parent.verticalCenter
                            color: PlayerTheme.textSoft
                            opacity: 0.8
                        }
                    }
                }
                handle: Rectangle {
                    x: timeline.leftPadding + timeline.visualPosition
                       * (timeline.availableWidth - width)
                    y: timeline.topPadding + timeline.availableHeight / 2 - height / 2
                    width: timeline.scrubbing || timeline.previewActive ? 16 : 12
                    height: width
                    radius: width / 2
                    color: PlayerTheme.projectorGoldBright
                    opacity: timeline.previewActive
                             ? PlayerTheme.playerGoldActiveOpacity
                             : PlayerTheme.playerGoldProgressOpacity
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                CpIconButton {
                    iconSource: "qrc:/icons/previous-file.svg"
                    label: root.neighborLabel(-1)
                    enabled: root.queueIndex > 0 && !playerBridge.switching && !playerBridge.resumeDecisionPending
                    onClicked: root.selectFile(root.queueIndex - 1, false)
                }
                CpIconButton {
                    iconSource: mpv.paused
                                ? "qrc:/icons/play.svg"
                                : "qrc:/icons/pause.svg"
                    label: mpv.paused ? "Play" : "Pause"
                    onClicked: {
                        mpv.togglePause()
                        root.showControls()
                    }
                }
                CpIconButton {
                    iconSource: "qrc:/icons/next-file.svg"
                    label: root.neighborLabel(1)
                    enabled: root.queueIndex >= 0 && root.queueIndex + 1 < root.queueItems.length && !playerBridge.switching && !playerBridge.resumeDecisionPending
                    onClicked: root.selectFile(root.queueIndex + 1, false)
                }
                CpIconButton {
                    iconSource: mpv.muted
                                ? "qrc:/icons/volume-muted.svg"
                                : "qrc:/icons/volume-high.svg"
                    label: mpv.muted ? "Unmute" : "Mute"
                    selected: mpv.muted
                    onClicked: {
                        mpv.toggleMute()
                        root.showControls()
                    }
                }
                Slider {
                    id: volumeSlider
                    Layout.preferredWidth: 118
                    Layout.preferredHeight: 32
                    from: 0
                    to: 100
                    value: mpv.volume
                    onMoved: mpv.setVolume(value)
                    background: Rectangle {
                        x: volumeSlider.leftPadding
                        y: volumeSlider.topPadding
                           + volumeSlider.availableHeight / 2 - height / 2
                        width: volumeSlider.availableWidth
                        height: 3
                        radius: 2
                        color: "#556d7178"
                        Rectangle {
                            width: parent.width * volumeSlider.visualPosition
                            height: parent.height
                            radius: parent.radius
                            color: PlayerTheme.projectorGold
                            opacity: volumeSlider.hovered || volumeSlider.pressed
                                     ? PlayerTheme.playerGoldActiveOpacity
                                     : PlayerTheme.playerGoldProgressOpacity
                        }
                    }
                    handle: Rectangle {
                        x: volumeSlider.leftPadding + volumeSlider.visualPosition
                           * (volumeSlider.availableWidth - width)
                        y: volumeSlider.topPadding
                           + volumeSlider.availableHeight / 2 - height / 2
                        width: volumeSlider.pressed || volumeSlider.hovered ? 14 : 11
                        height: width
                        radius: width / 2
                        color: PlayerTheme.projectorGoldBright
                        opacity: volumeSlider.hovered || volumeSlider.pressed
                                 ? PlayerTheme.playerGoldActiveOpacity
                                 : PlayerTheme.playerGoldProgressOpacity
                        border.width: 1
                        border.color: root.colorWithOpacity(
                            PlayerTheme.projectorGold,
                            PlayerTheme.playerGoldDecorativeOpacity)

                        Behavior on width { NumberAnimation { duration: 100 } }
                    }
                }
                Text {
                    text: root.formatTime(mpv.position) + " / " + root.formatTime(mpv.duration)
                    color: PlayerTheme.projectorGoldBright
                    opacity: PlayerTheme.playerGoldRestOpacity
                    font.pixelSize: 13
                }
                Item { Layout.fillWidth: true }
                AbstractButton {
                    id: speedButton
                    Layout.preferredWidth: 42
                    Layout.preferredHeight: 42
                    hoverEnabled: true
                    focusPolicy: Qt.StrongFocus
                    Accessible.name: "Playback speed " + mpv.speed.toFixed(2)
                    onClicked: {
                        root.sidePanelMode = ""
                        root.upNextSeconds = 0
                        if (speedPanel.opened) {
                            speedPanel.close()
                        } else {
                            audioPanelOpen = false
                            subtitlePanelOpen = false
                            chapterPanelOpen = false
                            subtitleSearchOpen = false
                            statisticsOpen = false
                            speedPanel.open()
                        }
                        root.showControls()
                    }
                    contentItem: Item {
                        Image {
                            anchors.horizontalCenter: parent.horizontalCenter
                            y: 3
                            width: 21
                            height: 21
                            source: "qrc:/icons/speed.svg"
                            fillMode: Image.PreserveAspectFit
                            sourceSize.width: 46
                            sourceSize.height: 46
                            opacity: speedButton.hovered || speedButton.activeFocus
                                     || speedPanel.opened
                                     ? PlayerTheme.playerGoldActiveOpacity
                                     : PlayerTheme.playerGoldRestOpacity
                            Behavior on opacity { NumberAnimation { duration: 120 } }
                        }
                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            y: 20
                            text: mpv.speed.toFixed(2) + "×"
                            color: PlayerTheme.projectorGoldBright
                            opacity: speedButton.hovered || speedButton.activeFocus
                                     || speedPanel.opened
                                     ? PlayerTheme.playerGoldActiveOpacity
                                     : PlayerTheme.playerGoldRestOpacity
                            font.pixelSize: 10
                        }
                    }
                    ToolTip.visible: speedButton.hovered
                    ToolTip.delay: 450
                    ToolTip.text: "Playback speed"
                }
                CpAudioTracksButton {
                    visible: mpv.audioTracks.length > 1
                    trackCount: mpv.audioTracks.length
                    selected: audioPanelOpen
                    onClicked: {
                        root.sidePanelMode = ""
                        root.upNextSeconds = 0
                        audioPanelOpen = !audioPanelOpen
                        subtitlePanelOpen = false
                        chapterPanelOpen = false
                        subtitleSearchOpen = false
                        speedPanel.close()
                        root.showControls()
                    }
                }
                CpIconButton {
                    iconSource: "qrc:/icons/subtitles.svg"
                    label: "Subtitles"
                    selected: subtitlePanelOpen
                    onClicked: {
                        root.sidePanelMode = ""
                        root.upNextSeconds = 0
                        subtitlePanelOpen = !subtitlePanelOpen
                        audioPanelOpen = false
                        chapterPanelOpen = false
                        subtitleSearchOpen = false
                        speedPanel.close()
                        root.showControls()
                    }
                }
                CpIconButton {
                    visible: root.hasPlaylist
                    focusPolicy: visible ? Qt.StrongFocus : Qt.NoFocus
                    iconSource: "qrc:/icons/playlist.svg"
                    label: "Playlist"
                    selected: root.sidePanelMode === "playlist"
                    onClicked: root.openSidePanel("playlist")
                }
                CpIconButton {
                    iconSource: "qrc:/icons/settings.svg"
                    label: "Settings"
                    selected: root.sidePanelMode === "settings" || root.sidePanelMode === "shortcuts"
                    onClicked: root.openSidePanel("settings")
                }
                CpIconButton {
                    iconSource: root.visibility === Window.FullScreen
                                ? "qrc:/icons/exit-fullscreen.svg"
                                : "qrc:/icons/enter-fullscreen.svg"
                    label: root.visibility === Window.FullScreen
                           ? "Exit fullscreen"
                           : "Enter fullscreen"
                    onClicked: root.toggleFullscreen()
                }
            }
        }

        Rectangle {
            id: timelinePreview
            z: 100
            visible: bottomBar.visible && timeline.previewActive
            width: 220
            height: timeline.hoverThumbnail.length > 0 ? 154 : 42
            x: Math.max(12, Math.min(
                bottomBar.width - width - 12,
                timeline.mapToItem(
                    bottomBar,
                    timeline.previewX,
                    0
                ).x - width / 2
            ))
            y: timeline.mapToItem(bottomBar, 0, 0).y - height - 8
            radius: PlayerTheme.radiusMedium
            color: PlayerTheme.panelBlack
            border.color: PlayerTheme.borderStrong
            Image {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 6
                height: 118
                visible: timeline.hoverThumbnail.length > 0
                source: timeline.hoverThumbnail
                fillMode: Image.PreserveAspectFit
                asynchronous: true
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 7
                text: root.formatTime(timeline.hoverPosition)
                color: PlayerTheme.textSoft
                font.pixelSize: 12
            }
        }
    }

    CpMenuPopup {
        id: playerSidePanel
        objectName: "playerSidePanel"
        parent: Overlay.overlay
        visible: root.sidePanelMode.length > 0
        x: root.width - width - 20
        y: 70
        width: Math.min(440, root.width - 40)
        height: Math.max(200, root.height - bottomBar.height - 92)
        onClosed: { root.sidePanelMode = ""; root.showControls() }
        background: Rectangle {
            radius: PlayerTheme.radiusMedium
            color: PlayerTheme.panelBlack
            border.color: PlayerTheme.borderStrong
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 16
            spacing: 10
            RowLayout {
                Layout.fillWidth: true
                Text {
                    text: root.sidePanelMode === "playlist" ? (playerBridge.queue.title || "Playlist")
                          : root.sidePanelMode === "shortcuts" ? "Keyboard shortcuts" : "Settings"
                    color: PlayerTheme.textSoft
                    font.pixelSize: 18
                    font.weight: Font.DemiBold
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }
                CpButton {
                    text: root.sidePanelMode === "shortcuts" ? "Back" : "Close"
                    compact: true
                    onClicked: {
                        root.sidePanelMode = root.sidePanelMode === "shortcuts" ? "settings" : ""
                        root.showControls()
                    }
                }
            }
            Text {
                Layout.fillWidth: true
                visible: (root.sidePanelMode === "playlist" || root.sidePanelMode === "settings")
                         && (playerBridge.queueError.length > 0 || Boolean(playerBridge.queue.autoplay_blocked_reason))
                text: playerBridge.queueError
                      || playerBridge.queue.autoplay_blocked_reason || ""
                color: PlayerTheme.projectorGoldBright
                wrapMode: Text.WordWrap
                font.pixelSize: 12
            }
            Text {
                Layout.fillWidth: true
                visible: root.sidePanelMode === "playlist"
                text: playerBridge.switching ? "Opening file…" : "Select an episode or movie to play"
                color: PlayerTheme.textMuted
                font.pixelSize: 12
            }
            CpScrollView {
                id: sideScroll
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                rightPadding: 10
                contentWidth: availableWidth
                Column {
                    id: sideColumn
                    width: sideScroll.availableWidth
                    spacing: 6
                    CpPlaylistContent {
                        id: playlistContent
                        width: parent.width
                        visible: root.sidePanelMode === "playlist"
                        items: root.queueItems
                        currentIndex: root.playingQueueIndex
                        mediaType: playerBridge.mediaType
                        switching: playerBridge.switching
                        resumeDecisionPending: playerBridge.resumeDecisionPending
                        onItemSelected: index => root.selectFile(index, false)
                        onEnsureVisibleRequested: target => {
                            if (visible) root.ensureSideItemVisible(target)
                        }
                    }
                    Repeater {
                        model: root.sidePanelMode === "settings" ? root.settingsActions : []
                        delegate: Column {
                            required property var modelData
                            required property int index
                            width: parent.width
                            spacing: 5
                            Text {
                                visible: index === 0 || root.settingsActions[index - 1].section !== modelData.section
                                text: modelData.section
                                color: PlayerTheme.projectorGoldBright
                                font.pixelSize: 11
                                topPadding: 12
                                bottomPadding: 3
                            }
                            CpButton {
                                width: parent.width
                                compact: true
                                text: modelData.title + (modelData.value ? "  ·  " + modelData.value : "")
                                      + (playerBridge.shortcuts[modelData.action] ? "    [" + playerBridge.shortcuts[modelData.action] + "]" : "")
                                highlighted: (modelData.action === "always_on_top" && root.alwaysOnTop)
                                             || (modelData.action === "autoplay" && playerBridge.autoplay)
                                enabled: !playerBridge.switching && !playerBridge.resumeDecisionPending
                                onClicked: root.runPlayerAction(modelData.action)
                            }
                        }
                    }
                    Repeater {
                        model: root.sidePanelMode === "shortcuts" ? Object.keys(playerBridge.shortcuts) : []
                        delegate: RowLayout {
                            required property string modelData
                            width: parent.width
                            height: 34
                            Text {
                                Layout.fillWidth: true
                                text: {
                                    const named = root.settingsActions.find(row => row.action === modelData)
                                    if (named) return named.title
                                    const labels = { play_pause: "Play / Pause", volume_up: "Volume up", volume_down: "Volume down", mute: "Mute", fullscreen: "Fullscreen", audio_tracks: "Audio tracks", subtitle_tracks: "Subtitle tracks", speed_down: "Slower playback", speed_up: "Faster playback" }
                                    return labels[modelData] || modelData.replace(/_/g, " ")
                                }
                                color: PlayerTheme.textSoft
                                font.pixelSize: 12
                                elide: Text.ElideRight
                            }
                            Text {
                                text: playerBridge.shortcuts[modelData] || ""
                                color: PlayerTheme.projectorGoldBright
                                font.pixelSize: 12
                            }
                        }
                    }
                    Text {
                        visible: root.sidePanelMode === "shortcuts"
                        width: parent.width
                        text: "Esc closes the open panel or exits fullscreen. Enter toggles fullscreen. Change shortcuts in CP’s Player settings."
                        color: PlayerTheme.textMuted
                        wrapMode: Text.WordWrap
                        font.pixelSize: 12
                        topPadding: 12
                    }
                }
            }
        }
    }

    Rectangle {
        id: upNextPanel
        enabled: !root.dismissalGuardActive
        objectName: "upNextPanel"
        z: 190
        visible: root.upNextSeconds > 0
        anchors.horizontalCenter: parent.horizontalCenter
        y: Math.max(30, bottomBar.y - height - 20)
        width: Math.min(520, root.width - 48)
        height: upNextContent.implicitHeight + 32
        radius: PlayerTheme.radiusMedium
        color: PlayerTheme.panelBlack
        border.color: PlayerTheme.projectorGold
        ColumnLayout {
            id: upNextContent
            anchors.fill: parent
            anchors.margins: 16
            spacing: 10
            Text {
                text: "UP NEXT IN " + root.upNextSeconds + " SECONDS"
                color: PlayerTheme.projectorGoldBright
                font.pixelSize: 11
            }
            Text {
                Layout.fillWidth: true
                text: root.queueItems[root.queueIndex + 1] ? root.queueItems[root.queueIndex + 1].title : ""
                color: PlayerTheme.textSoft
                font.pixelSize: 16
                wrapMode: Text.WordWrap
            }
            RowLayout {
                CpButton { text: "Play now"; highlighted: true; onClicked: root.selectFile(root.queueIndex + 1, true) }
                CpButton { text: "Cancel"; onClicked: root.upNextSeconds = 0 }
            }
        }
    }

    CpMenuPopup {
        id: speedPanel
        parent: Overlay.overlay
        x: Math.max(28, root.width - width - 116)
        y: Math.max(20, root.height - bottomBar.height - height + 44)
        width: 220
        height: 176
        padding: 12
        property var presetSpeeds: [0.50, 0.75, 1.00, 1.25, 1.50, 2.00]
        onOpened: root.showControls()
        onClosed: root.showControls()

        background: Rectangle {
            color: root.colorWithOpacity(PlayerTheme.panelBlack, 0.75)
            radius: PlayerTheme.radiusLarge
            border.color: PlayerTheme.borderStrong
        }

        contentItem: ColumnLayout {
            spacing: 7
            Text {
                text: "Playback speed"
                color: PlayerTheme.textStrong
                font.pixelSize: 14
                font.weight: Font.DemiBold
            }
            GridLayout {
                Layout.fillWidth: true
                columns: 3
                rowSpacing: 4
                columnSpacing: 4
                Repeater {
                    model: speedPanel.presetSpeeds
                    delegate: CpButton {
                        required property real modelData
                        compact: true
                        Layout.fillWidth: true
                        text: modelData.toFixed(2) + "×"
                        highlighted: Math.abs(mpv.speed - modelData) < 0.001
                        onClicked: {
                            mpv.setSpeed(modelData)
                            root.showControls()
                        }
                    }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                CpButton {
                    compact: true
                    Layout.preferredWidth: 54
                    text: "−"
                    enabled: mpv.speed > 0.25
                    Accessible.name: "Decrease playback speed"
                    onClicked: {
                        mpv.setSpeed(mpv.speed - 0.05)
                        root.showControls()
                    }
                }
                Text {
                    Layout.fillWidth: true
                    text: mpv.speed.toFixed(2) + "×"
                    color: PlayerTheme.projectorGoldBright
                    opacity: PlayerTheme.playerGoldActiveOpacity
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                    horizontalAlignment: Text.AlignHCenter
                }
                CpButton {
                    compact: true
                    Layout.preferredWidth: 54
                    text: "+"
                    enabled: mpv.speed < 4.0
                    Accessible.name: "Increase playback speed"
                    onClicked: {
                        mpv.setSpeed(mpv.speed + 0.05)
                        root.showControls()
                    }
                }
            }
        }
    }

    CpMenuPopup {
        id: trackPanel
        objectName: "trackPanel"
        parent: Overlay.overlay
        width: Math.min(315, root.width - 56)
        height: Math.min(290, root.height - 210)
        x: root.width - width - 28
        y: bottomBar.y - height + 44
        visible: audioPanelOpen || subtitlePanelOpen || chapterPanelOpen
        onClosed: {
            root.audioPanelOpen = false
            root.subtitlePanelOpen = false
            root.chapterPanelOpen = false
            root.showControls()
        }
        background: Rectangle {
            color: root.colorWithOpacity(PlayerTheme.panelBlack, 0.75)
            radius: PlayerTheme.radiusLarge
            border.color: PlayerTheme.borderStrong
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 12
            spacing: 7

            Text {
                text: audioPanelOpen ? "Audio tracks"
                                     : subtitlePanelOpen ? "Subtitle tracks" : "Chapters"
                color: PlayerTheme.textStrong
                font.pixelSize: 14
                font.weight: Font.DemiBold
            }
            Rectangle { Layout.fillWidth: true; height: 1; color: PlayerTheme.border }
            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true

                CpScrollView {
                    id: audioScroll
                    anchors.fill: parent
                    visible: audioPanelOpen
                    Column {
                        width: audioScroll.availableWidth
                        spacing: 4
                        Repeater {
                            model: mpv.audioTracks
                            delegate: CpButton {
                                required property var modelData
                                compact: true
                                width: parent.width
                                text: root.trackLabel(modelData)
                                highlighted: !!modelData.selected
                                onClicked: {
                                    mpv.selectAudioTrack(modelData.id)
                                    root.closeOverlays()
                                }
                            }
                        }
                        Text {
                            width: parent.width
                            visible: mpv.audioTracks.length === 0
                            text: "No audio tracks are available."
                            color: PlayerTheme.textMuted
                            wrapMode: Text.WordWrap
                            padding: 12
                        }
                    }
                }

                CpScrollView {
                    id: subtitleScroll
                    anchors.fill: parent
                    visible: subtitlePanelOpen
                    Column {
                        width: subtitleScroll.availableWidth
                        spacing: 4
                        CpButton {
                            compact: true
                            width: parent.width
                            text: "Find subs"
                            rightIconSource: "qrc:/icons/search.svg"
                            highlighted: true
                            onClicked: root.showSubtitleSearch()
                        }
                        CpButton {
                            compact: true
                            width: parent.width
                            visible: playerBridge.selectedSubtitleCanSave
                                     || playerBridge.subtitleSaveStatus === "saving"
                                     || playerBridge.subtitleSaveStatus === "saved"
                            enabled: playerBridge.selectedSubtitleCanSave
                                     && playerBridge.subtitleSaveStatus !== "saving"
                            text: playerBridge.subtitleSaveStatus === "saving"
                                  ? "Saving subtitle..."
                                  : playerBridge.subtitleSaveStatus === "saved"
                                    ? "Saved beside movie"
                                    : "Save subs"
                            rightIconSource: "qrc:/icons/download.svg"
                            onClicked: playerBridge.requestSaveSelectedSubtitle()
                        }
                        Text {
                            width: parent.width
                            visible: playerBridge.subtitleSaveError.length > 0
                            text: playerBridge.subtitleSaveError
                            color: PlayerTheme.dangerRed
                            wrapMode: Text.WordWrap
                            padding: 8
                        }
                        Rectangle {
                            width: parent.width
                            height: 1
                            color: PlayerTheme.border
                        }
                        CpButton {
                            compact: true
                            width: parent.width
                            text: "Off"
                            onClicked: {
                                mpv.disableSubtitles()
                                subtitlePanelOpen = false
                            }
                        }
                        Repeater {
                            model: mpv.subtitleTracks
                            delegate: CpButton {
                                required property var modelData
                                compact: true
                                width: parent.width
                                text: root.trackLabel(modelData)
                                highlighted: !!modelData.selected
                                onClicked: {
                                    mpv.selectSubtitleTrack(modelData.id)
                                    root.closeOverlays()
                                }
                            }
                        }
                        Text {
                            width: parent.width
                            visible: mpv.subtitleTracks.length === 0
                            text: "No subtitle tracks are available."
                            color: PlayerTheme.textMuted
                            wrapMode: Text.WordWrap
                            padding: 12
                        }
                    }
                }

                CpScrollView {
                    id: chapterScroll
                    anchors.fill: parent
                    visible: chapterPanelOpen
                    Column {
                        width: chapterScroll.availableWidth
                        spacing: 4
                        Repeater {
                            model: mpv.chapters
                            delegate: CpButton {
                                required property var modelData
                                compact: true
                                width: parent.width
                                text: (modelData.title || "Chapter") + "  ·  "
                                      + root.formatTime(modelData.time)
                                onClicked: {
                                    mpv.seekAbsolute(modelData.time)
                                    root.closeOverlays()
                                }
                            }
                        }
                        Text {
                            width: parent.width
                            visible: mpv.chapters.length === 0
                            text: "No chapters are available."
                            color: PlayerTheme.textMuted
                            wrapMode: Text.WordWrap
                            padding: 12
                        }
                    }
                }
            }
        }
    }

    Rectangle {
        z: 20
        width: Math.min(560, root.width - 56)
        height: 260
        anchors.centerIn: parent
        visible: playerBridge.resumeDecisionPending
        enabled: !root.dismissalGuardActive
        color: PlayerTheme.panelBlack
        radius: PlayerTheme.radiusExtraLarge
        border.color: root.colorWithOpacity(
            PlayerTheme.projectorGold,
            PlayerTheme.playerGoldDecorativeOpacity)

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 28
            spacing: 14
            Text {
                text: "Continue watching?"
                color: PlayerTheme.textStrong
                font.pixelSize: 24
                font.weight: Font.DemiBold
            }
            Text {
                Layout.fillWidth: true
                text: "Cinema Paradiso saved your place at "
                      + root.formatTime(playerBridge.resumePositionMs / 1000) + "."
                color: PlayerTheme.textSoft
                font.pixelSize: 15
                wrapMode: Text.WordWrap
            }
            Item { Layout.fillHeight: true }
            RowLayout {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignRight
                spacing: 10
                CpButton {
                    text: "Start over"
                    onClicked: playerBridge.chooseRestart()
                }
                CpButton {
                    text: "Resume from " + root.formatTime(playerBridge.resumePositionMs / 1000)
                    highlighted: true
                    onClicked: playerBridge.chooseResume()
                }
            }
        }
    }

    CpMenuPopup {
        id: subtitleSearchPanel
        objectName: "subtitleSearchPanel"
        parent: Overlay.overlay
        width: Math.min(760, root.width - 56)
        height: Math.min(570, root.height - 72)
        x: (root.width - width) / 2
        y: (root.height - height) / 2
        visible: subtitleSearchOpen
        onClosed: { root.subtitleSearchOpen = false; root.showControls() }
        background: Rectangle {
            color: PlayerTheme.panelBlack
            radius: PlayerTheme.radiusExtraLarge
            border.color: root.colorWithOpacity(PlayerTheme.projectorGold, PlayerTheme.playerGoldDecorativeOpacity)
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 24
            spacing: 12
            Text {
                text: "Find subtitles"
                color: PlayerTheme.textStrong
                font.pixelSize: 22
                font.weight: Font.DemiBold
            }
            Text {
                Layout.fillWidth: true
                text: playerBridge.subtitleSearchStatus === "searching"
                      ? "Searching your configured providers…"
                      : playerBridge.subtitleSearchStatus === "downloading"
                        ? "Downloading and validating the selected subtitle…"
                        : playerBridge.subtitleSearchStatus === "loaded"
                          ? "Subtitle loaded. Verify it, then use the subtitle icon to save it beside the movie."
                          : playerBridge.subtitleResults.length === 0
                            ? "No matching subtitles were returned by the configured providers."
                            : playerBridge.subtitleResults.length + " ranked results"
                color: PlayerTheme.textSoft
                wrapMode: Text.WordWrap
                lineHeight: 1.2
            }
            Text {
                Layout.fillWidth: true
                visible: playerBridge.subtitleSearchError.length > 0
                text: playerBridge.subtitleSearchError
                color: PlayerTheme.dangerRed
                wrapMode: Text.WordWrap
            }
            ListView {
                id: subtitleResultList
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                spacing: 8
                model: playerBridge.subtitleResults
                flickableDirection: Flickable.VerticalFlick
                contentWidth: width
                ScrollBar.vertical: CpRevealScrollBar { viewport: subtitleResultList; flickable: subtitleResultList }
                delegate: Rectangle {
                    required property var modelData
                    width: subtitleResultList.width - 10
                    height: 92
                    radius: PlayerTheme.radiusMedium
                    color: resultHover.hovered
                           ? PlayerTheme.surfaceRaised : PlayerTheme.archiveBlack
                    border.color: PlayerTheme.borderStrong

                    HoverHandler { id: resultHover; cursorShape: Qt.PointingHandCursor }
                    TapHandler {
                        onTapped: playerBridge.requestSubtitleDownload(modelData.result_id)
                    }
                    Column {
                        anchors.left: parent.left
                        anchors.right: providerLabel.left
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.leftMargin: 14
                        anchors.rightMargin: 12
                        spacing: 5
                        Text {
                            width: parent.width
                            text: modelData.release_name
                            color: PlayerTheme.textStrong
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                            elide: Text.ElideRight
                        }
                        Text {
                            width: parent.width
                            text: [
                                String(modelData.language || "und").toUpperCase(),
                                modelData.frame_rate > 0 ? Number(modelData.frame_rate).toFixed(3) + " fps" : "",
                                modelData.hearing_impaired ? "SDH" : "",
                                modelData.forced ? "Forced" : ""
                            ].filter(Boolean).join("  ·  ")
                            color: PlayerTheme.textSoft
                            font.pixelSize: 12
                            elide: Text.ElideRight
                        }
                        Text {
                            width: parent.width
                            text: modelData.match_reason
                            color: PlayerTheme.projectorGoldBright
                            opacity: PlayerTheme.playerGoldRestOpacity
                            font.pixelSize: 12
                            elide: Text.ElideRight
                        }
                    }
                    Text {
                        id: providerLabel
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.rightMargin: 14
                        width: 118
                        text: modelData.provider
                        elide: Text.ElideRight
                        color: PlayerTheme.textMuted
                        font.pixelSize: 12
                        horizontalAlignment: Text.AlignRight
                    }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                Text {
                    Layout.fillWidth: true
                    text: "Credentials stay in the Cinema Paradiso backend."
                    color: PlayerTheme.textMuted
                    font.pixelSize: 11
                }
                CpButton {
                    text: "Search again"
                    onClicked: playerBridge.requestSubtitleSearch()
                }
                CpButton { text: "Close"; onClicked: root.closeOverlays() }
            }
        }
    }

    CpMenuPopup {
        id: statisticsPanel
        objectName: "statisticsPanel"
        parent: Overlay.overlay
        width: 350
        height: 250
        x: root.width - width - 28
        y: topBar.height
        visible: statisticsOpen
        onClosed: { root.statisticsOpen = false; root.showControls() }
        background: Rectangle {
            color: PlayerTheme.panelBlack
            radius: PlayerTheme.radiusLarge
            border.color: root.colorWithOpacity(PlayerTheme.projectorGold, PlayerTheme.playerGoldDecorativeOpacity)
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 18
            spacing: 8
            Text {
                text: "Playback statistics"
                color: PlayerTheme.textStrong
                font.pixelSize: 18
                font.weight: Font.DemiBold
            }
            Repeater {
                model: [
                    ["Video", playbackStatistics.video_codec || "Unknown"],
                    ["Resolution", playbackStatistics.resolution || "Unknown"],
                    ["Frame rate", playbackStatistics.frame_rate || "Unknown"],
                    ["Hardware decoder", playbackStatistics.hardware_decoder || "Software"],
                    ["Audio", playbackStatistics.audio_codec || "Unknown"],
                    ["Display", playbackStatistics.display_fps
                                ? playbackStatistics.display_fps + " Hz" : "Unknown"]
                ]
                delegate: RowLayout {
                    required property var modelData
                    Layout.fillWidth: true
                    Text { text: modelData[0]; color: PlayerTheme.textMuted; Layout.preferredWidth: 125 }
                    Text { text: modelData[1]; color: PlayerTheme.textSoft; Layout.fillWidth: true; elide: Text.ElideRight }
                }
            }
            Item { Layout.fillHeight: true }
            Text {
                text: "I closes statistics"
                color: PlayerTheme.textFaint
                font.pixelSize: 11
            }
        }
    }

    Rectangle {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: bottomBar.top
        anchors.bottomMargin: 8
        visible: toastText.length > 0
        color: PlayerTheme.surfaceRaised
        radius: PlayerTheme.radiusMedium
        border.color: PlayerTheme.borderStrong
        width: toast.implicitWidth + 28
        height: 38
        Text {
            id: toast
            anchors.centerIn: parent
            text: toastText
            color: PlayerTheme.textSoft
            font.pixelSize: 13
        }
    }
}
