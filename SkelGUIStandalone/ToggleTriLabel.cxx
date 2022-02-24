#include <QtCore/QtGlobal>
#include <QVector>

#if QT_VERSION >= 0x050000
    #include <QtWidgets>
#else
    #include <QtGui>
#endif

#include "ToggleTriLabel.h"


ToggleTriLabel::ToggleTriLabel(std::vector<int> hideTriLabel, QWidget *parent)
    :QDialog(parent)
{
	int size = Global::vectorLabelInfo.size();
    /*for(int i = 0; i < 10; i++){
        QLabel *labelTemp = new QLabel(tr("Label %n", "", i+1));

        QCheckBox *checkBoxTemp = new QCheckBox(tr("Hide"));
		if(hideTriLabel[i]==1)
			checkBoxTemp->setChecked(true);


        QLabel *colorTemp = new QLabel;
		colorTemp->setPalette(QPalette(triLabelColors[i]));
		colorTemp->setAutoFillBackground(true);

        listLabel.append(labelTemp);
        listCheckBox.append(checkBoxTemp);
        listColorLabel.append(colorTemp);
    }*/

	for (int i = 0; i < size; i++) {
		std::string label = Global::vectorLabelInfo[i].labelName;
		QColor qc = Global::vectorLabelInfo[i].labelColor;

		QLabel *labelTemp = new QLabel(QString::number(i+1)+" "+QString::fromUtf8(label.data(), label.size()));
		
		QCheckBox *checkBoxTemp = new QCheckBox(tr("Hide"));
		if (hideTriLabel[i] == 1)
			checkBoxTemp->setChecked(true);

		QLabel *colorTemp = new QLabel;
		colorTemp->setPalette(QPalette(qc));
		colorTemp->setAutoFillBackground(true);

		listLabel.append(labelTemp);
		listCheckBox.append(checkBoxTemp);
		listColorLabel.append(colorTemp);
	}

    done = new QPushButton(tr("Done"));
    done->setDefault(true);

    QVector<QHBoxLayout*> triangle;
    for(int i = 0; i < size; i++){
        QHBoxLayout *triangleTemp = new QHBoxLayout;
        triangleTemp->addWidget(listCheckBox[i]);
        triangleTemp->addWidget(listLabel[i]);
        triangleTemp->addWidget(listColorLabel[i]);
        triangle.append(triangleTemp);
    }
    QVBoxLayout *layout = new QVBoxLayout;
    for(int i = 0; i < triangle.size(); i++){
        layout->addLayout(triangle[i]);
    }
    layout->addWidget(done);

    QGridLayout *mainLayout = new QGridLayout;
    mainLayout->addLayout(layout, 0, 0);
    setLayout(mainLayout);
    setWindowTitle(tr("Hide Triangle's label"));

    connect(done, SIGNAL(clicked()), this, SLOT(accept()));
	resize(250, 50);
}

void ToggleTriLabel::accept(){
    QDialog::accept();
}
