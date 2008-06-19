package no.uninett.nav.window;

import java.awt.*;
import javax.swing.*;
import javax.swing.border.*;

public class netboxTooltip extends JPanel {

	private JLabel sysnameLabel;
	private JLabel sysnameValue;
	private JLabel categoryLabel;
	private JLabel categoryValue;
	private JLabel typeLabel;
	private JLabel typeValue;
	private JLabel roomLabel;
	private JLabel roomValue;
	private JLabel cpuLabel;
	private JLabel cpuValue;

	public netboxTooltip() {
		initComponents();
	}

	public netboxTooltip(String sysname, String category, String type, String room, String cpuload){
		initComponents();
		this.sysnameValue.setText(sysname);
		this.categoryValue.setText(category);
		this.typeValue.setText(type);
		this.roomValue.setText(room);
		this.cpuValue.setText(cpuload);
	}

	public JLabel getSysnameValue() {
		return sysnameValue;
	}

	private void initComponents() {
		sysnameLabel = new JLabel();
		sysnameValue = new JLabel();
		categoryLabel = new JLabel();
		categoryValue = new JLabel();
		typeLabel = new JLabel();
		typeValue = new JLabel();
		roomLabel = new JLabel();
		roomValue = new JLabel();
		cpuLabel = new JLabel();
		cpuValue = new JLabel();

		setBorder(new LineBorder(new Color(33, 33, 33), 1, true));

		setLayout(new GridBagLayout());
		((GridBagLayout)getLayout()).columnWidths = new int[] {0, 0, 0};
		((GridBagLayout)getLayout()).rowHeights = new int[] {0, 0, 0, 0, 0, 0};
		((GridBagLayout)getLayout()).columnWeights = new double[] {0.0, 1.0, 1.0E-4};
		((GridBagLayout)getLayout()).rowWeights = new double[] {0.0, 0.0, 0.0, 0.0, 0.0, 1.0E-4};

		sysnameLabel.setText("Sysname:");
		sysnameLabel.setFont(sysnameLabel.getFont().deriveFont(Font.BOLD));
		add(sysnameLabel, new GridBagConstraints(0, 0, 1, 1, 0.0, 0.0,
			GridBagConstraints.CENTER, GridBagConstraints.BOTH,
			new Insets(0, 10, 5, 5), 0, 0));

		sysnameValue.setText("");
		sysnameValue.setHorizontalAlignment(SwingConstants.LEFT);
		add(sysnameValue, new GridBagConstraints(1, 0, 1, 1, 0.0, 0.0,
			GridBagConstraints.CENTER, GridBagConstraints.BOTH,
			new Insets(0, 10, 5, 10), 0, 0));

		categoryLabel.setText("Category:");
		categoryLabel.setFont(categoryLabel.getFont().deriveFont(Font.BOLD));
		add(categoryLabel, new GridBagConstraints(0, 1, 1, 1, 0.0, 0.0,
			GridBagConstraints.CENTER, GridBagConstraints.BOTH,
			new Insets(0, 10, 5, 5), 0, 0));

		categoryValue.setText("");
		add(categoryValue, new GridBagConstraints(1, 1, 1, 1, 0.0, 0.0,
			GridBagConstraints.CENTER, GridBagConstraints.BOTH,
			new Insets(0, 10, 5, 10), 0, 0));

		typeLabel.setText("Type:");
		typeLabel.setFont(typeLabel.getFont().deriveFont(Font.BOLD));
		add(typeLabel, new GridBagConstraints(0, 2, 1, 1, 0.0, 0.0,
			GridBagConstraints.CENTER, GridBagConstraints.BOTH,
			new Insets(0, 10, 5, 5), 0, 0));

		typeValue.setText("");
		add(typeValue, new GridBagConstraints(1, 2, 1, 1, 0.0, 0.0,
			GridBagConstraints.CENTER, GridBagConstraints.BOTH,
			new Insets(0, 10, 5, 10), 0, 0));

		roomLabel.setText("Room:");
		roomLabel.setFont(roomLabel.getFont().deriveFont(Font.BOLD));
		add(roomLabel, new GridBagConstraints(0, 3, 1, 1, 0.0, 0.0,
			GridBagConstraints.CENTER, GridBagConstraints.BOTH,
			new Insets(0, 10, 5, 5), 0, 0));

		roomValue.setText("");
		add(roomValue, new GridBagConstraints(1, 3, 1, 1, 0.0, 0.0,
			GridBagConstraints.CENTER, GridBagConstraints.BOTH,
			new Insets(0, 10, 5, 10), 0, 0));

		cpuLabel.setText("CPU Load:");
		cpuLabel.setFont(cpuLabel.getFont().deriveFont(Font.BOLD));
		add(cpuLabel, new GridBagConstraints(0, 4, 1, 1, 0.0, 0.0,
			GridBagConstraints.CENTER, GridBagConstraints.BOTH,
			new Insets(0, 10, 0, 5), 0, 0));

		cpuValue.setText("");
		add(cpuValue, new GridBagConstraints(1, 4, 1, 1, 0.0, 0.0,
			GridBagConstraints.CENTER, GridBagConstraints.BOTH,
			new Insets(0, 10, 0, 10), 0, 0));
	}
}