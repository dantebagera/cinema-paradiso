import QtQuick
import QtQuick.Controls.Basic

Button {
    id: control
    property bool compact: false
    property url rightIconSource: ""
    leftPadding: compact ? 10 : 14
    rightPadding: (compact ? 10 : 14)
                  + (rightIconSource.toString().length > 0 ? 22 : 0)
    topPadding: compact ? 7 : 9
    bottomPadding: compact ? 7 : 9
    contentItem: Text {
        text: control.text
        color: control.highlighted ? PlayerTheme.projectorGoldBright : PlayerTheme.textSoft
        font.pixelSize: control.compact ? 11 : 13
        font.weight: control.highlighted ? Font.DemiBold : Font.Normal
        elide: Text.ElideRight
        horizontalAlignment: Text.AlignLeft
        verticalAlignment: Text.AlignVCenter
    }
    background: Rectangle {
        radius: PlayerTheme.radiusMedium
        color: control.down ? PlayerTheme.surfaceRaised
                            : control.hovered ? "#ff26282d" : PlayerTheme.panelBlack
        border.color: control.highlighted ? PlayerTheme.projectorGold
                                          : PlayerTheme.borderStrong

        Image {
            visible: control.rightIconSource.toString().length > 0
            anchors.right: parent.right
            anchors.rightMargin: control.compact ? 10 : 14
            anchors.verticalCenter: parent.verticalCenter
            width: control.compact ? 16 : 18
            height: width
            source: control.rightIconSource
            fillMode: Image.PreserveAspectFit
            opacity: control.enabled
                     ? PlayerTheme.playerGoldRestOpacity
                     : PlayerTheme.playerGoldDisabledOpacity
        }
    }
}

