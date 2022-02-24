#ifndef TOGGLETRILABEL_H
#define TOGGLETRILABEL_H

#include <QDialog>
#include "global.h"

QT_BEGIN_NAMESPACE
class QDialogButtonBox;
//class QGroupBox;
class QLabel;
class QPushButton;
class QCheckBox;
QT_END_NAMESPACE

//! [0]
class ToggleTriLabel : public QDialog
{
    Q_OBJECT

public:
    ToggleTriLabel(std::vector<int> hideTriLabel, QWidget *parent = 0);

    //List of label
    QVector<QLabel*> listLabel;

    //List of checkbox
    QVector<QCheckBox*> listCheckBox;

    //List of color label
    QVector<QLabel*> listColorLabel;

    //Done Button
    QPushButton *done;

    private slots:
        void accept();
};
//! [0]



#endif
