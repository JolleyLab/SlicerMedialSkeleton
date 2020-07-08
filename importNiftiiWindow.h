#ifndef IMPORTNIFTIIWINDOW_H
#define IMPORTNIFTIIWINDOW_H

#include <QDialog>
#include "global.h"

QT_BEGIN_NAMESPACE
class QDialogButtonBox;
class QGroupBox;
class QLabel;
class QLineEdit;
class QPushButton;
class QCheckBox;
QT_END_NAMESPACE

//! [0]
class importNiftiiWindow : public QDialog
{
    Q_OBJECT

public:
    importNiftiiWindow(QWidget *parent = 0);

    QLabel *inputLabel;
    QLineEdit *inputEdit;
    QPushButton *inputBrowse;

    QLabel *outputLabel;
    QLineEdit *outputEdit;
    QPushButton *outputBrowse;

    QCheckBox *smoothCheck;
    QLabel *sigmaLabel;
    QLineEdit *sigmaEdit;

    QLabel *threshLabel1;
    QLabel *u11Label;
    QLineEdit *u11;
    QLabel *u21Label;
    QLineEdit *u21;

    QLabel *threshLabel2;
    QLabel *u12Label;
    QLineEdit *u12;
    QLabel *u22Label;
    QLineEdit *u22;

	QPushButton *showAdvancedParams;
	QPushButton *hideAdvancedParams;
    QPushButton *done;

    private slots:
        void accept();
		void checked();
        void browseInput();
        void browseOutput();
		void hideParams();
		void showParams();
};
//! [0]
#endif // IMPORTNIFTIIWINDOW_H
