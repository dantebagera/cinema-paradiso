import QtQuick
import QtQuick.Controls
import QtTest
import CinemaParadiso.Player 1.0

TestCase {
    id: test
    name: "MenuDismissal"
    width: 600; height: 500
    visible: true
    when: windowShown
    property int backgroundClicks: 0
    property int insideClicks: 0
    property int backgroundDoubleClicks: 0
    property int menuClosedCount: 0
    MouseArea {
        anchors.fill: parent
        enabled: !menu.dismissalGuardActive && !replacement.dismissalGuardActive
        onClicked: test.backgroundClicks++
        onDoubleClicked: test.backgroundDoubleClicks++
    }
    CpMenuPopup {
        id: menu; x: 100; y: 100; width: 200; height: 200
        onClosed: test.menuClosedCount++ // Main owns a derived close-state handler too.
        CpButton { id: inside; text: "Inside"; onClicked: test.insideClicks++ }
    }
    CpMenuPopup {
        id: replacement; x: 100; y: 100; width: 200; height: 200
        onClosed: test.menuClosedCount++
    }
    property bool menuRequested: false
    CpMenuPopup { id: boundMenu; x: 100; y: 100; width: 200; height: 200; visible: test.menuRequested; onClosed: test.menuRequested = false }
    CpButton { id: opener; x: 350; y: 20; text: "Open menu"; onClicked: test.menuRequested = !test.menuRequested }
    function init() { backgroundClicks = 0; insideClicks = 0; menu.open(); tryCompare(menu, "opened", true) }
    function cleanup() { menu.close(); replacement.close(); boundMenu.close(); wait(Qt.styleHints.mouseDoubleClickInterval + 20) }
    function test_outsideGestureConsumed() {
        mousePress(test, 400, 350)
        verify(menu.visible, "Dismiss on completed click, keeping playback blocked through release")
        mouseRelease(test, 400, 350)
        tryCompare(menu, "visible", false)
        compare(backgroundClicks, 0)
        wait(Qt.styleHints.mouseDoubleClickInterval + 20)
        tryCompare(menu, "dismissalGuardActive", false)
        tryCompare(replacement, "dismissalGuardActive", false)
        mouseClick(test, 400, 350)
        compare(backgroundClicks, 1, "guard=" + menu.dismissalGuardActive + "/" + replacement.dismissalGuardActive + ", doubles=" + backgroundDoubleClicks)
    }
    function test_insideActionAndBlankSpace() {
        mouseClick(inside)
        compare(insideClicks, 1)
        verify(!menu.dismissalGuardActive, "Inside actions must not arm the outside-dismiss guard")
        verify(menu.visible)
        mouseClick(menu.contentItem, 160, 160)
        verify(menu.visible)
        compare(backgroundClicks, 0)
    }
    function test_escapeExplicitCloseAndReopen() {
        keyClick(Qt.Key_Escape)
        tryCompare(menu, "visible", false)
        menu.open(); tryCompare(menu, "opened", true)
        menu.close(); tryCompare(menu, "visible", false)
        mouseClick(test, 400, 350)
        compare(backgroundClicks, 1, "guard=" + menu.dismissalGuardActive + "/" + replacement.dismissalGuardActive + ", doubles=" + backgroundDoubleClicks)
    }
    function test_dragBegunInsideDoesNotDismiss() {
        mousePress(menu.contentItem, 160, 160)
        mouseMove(test, 450, 350)
        mouseRelease(test, 450, 350)
        verify(menu.visible)
        compare(backgroundClicks, 0)
    }
    function test_replacementDoesNotLeaveBlocker() {
        menu.close(); replacement.open()
        tryCompare(replacement, "opened", true)
        mouseClick(test, 400, 350)
        tryCompare(replacement, "visible", false)
        compare(backgroundClicks, 0)
        wait(Qt.styleHints.mouseDoubleClickInterval + 20)
        tryCompare(menu, "dismissalGuardActive", false)
        tryCompare(replacement, "dismissalGuardActive", false)
        mouseClick(test, 400, 350)
        compare(backgroundClicks, 1, "guard=" + menu.dismissalGuardActive + "/" + replacement.dismissalGuardActive + ", doubles=" + backgroundDoubleClicks)
    }
    function test_outsideDoubleClickDoesNotActivateBackground() {
        mouseDoubleClickSequence(test, 400, 350)
        tryCompare(menu, "visible", false)
        compare(backgroundClicks, 0)
        compare(backgroundDoubleClicks, 0)
    }
    function test_openingButtonDoesNotDismissItsOwnMenu() {
        menu.close()
        mouseClick(opener)
        wait(100)
        verify(boundMenu.visible, "The opening release must not count as an outside dismissal")
    }
}
