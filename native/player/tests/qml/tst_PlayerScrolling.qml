import QtQuick
import QtQuick.Controls
import QtTest
import CinemaParadiso.Player 1.0

TestCase {
    name: "PlayerScrolling"
    width: 600; height: 500
    visible: true
    when: windowShown
    Component {
        id: factory
        CpScrollView {
            width: 250; height: 220
            Column {
                width: parent.availableWidth
                Repeater { model: 40; CpButton { width: 240; text: "Long label · العربية · " + index } }
            }
        }
    }
    property var view
    function init() { view = createTemporaryObject(factory, this); mouseMove(this, 500, 450); wait(200) }
    function test_dragWidthAndPaint() {
        compare(view.verticalBar.width, 8)
        compare(view.verticalBar.contentItem.width, 2)
        compare(view.ScrollBar.horizontal.policy, ScrollBar.AlwaysOff)
        compare(view.contentWidth, view.availableWidth)
    }
    function test_noOverflowNoBar() {
        view.contentHeight = 20
        wait(20)
        verify(!view.verticalBar.visible)
    }
    function test_revealOnHover() {
        mouseMove(view, 100, 100)
        tryCompare(view.verticalBar.contentItem, "opacity", 0.72)
        mouseMove(this, 500, 450)
        tryCompare(view.verticalBar.contentItem, "opacity", 0)
    }
    function test_scrollActivitySurvives900ms() {
        view.contentItem.contentY = 100
        wait(150)
        verify(view.verticalBar.contentItem.opacity > 0)
        wait(500)
        verify(view.verticalBar.contentItem.opacity > 0)
        wait(500)
        compare(view.verticalBar.contentItem.opacity, 0)
        verify(view.contentItem.contentY > 0)
    }
    function test_keyboardFocusReveals() {
        view.contentItem.contentItem.children[0].forceActiveFocus()
        tryCompare(view.verticalBar.contentItem, "opacity", 0.72)
    }
    function test_wheelAndDragReachLongContent() {
        mouseWheel(view, 100, 100, 0, -480)
        tryVerify(() => view.contentItem.contentY > 0)
        let bar = view.verticalBar
        mousePress(bar, 4, bar.contentItem.y + 3)
        mouseMove(bar, 4, bar.height - 5, 200)
        mouseRelease(bar, 4, bar.height - 5)
        verify(view.contentItem.contentY > 500)
        compare(view.contentWidth, view.availableWidth)
    }
}
