#include <QtQuickTest/quicktest.h>
#include <QtQuickControls2/QQuickStyle>
class Setup : public QObject {
    Q_OBJECT
public slots:
    void applicationAvailable() { QQuickStyle::setStyle(QStringLiteral("Basic")); }
};
QUICK_TEST_MAIN_WITH_SETUP(cp_player_ui, Setup)
#include "ui_main.moc"
