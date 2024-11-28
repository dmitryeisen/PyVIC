# PyVIC

PyVIC (Python Virtual Input Console) ist eine Anwendung zur Simulation von HID-Geräten (Tastatur und Maus) und zur Echtzeit-Anzeige von Bildschirmdaten durch Kamera-Capturing. Dieses Tool bietet eine einfache Möglichkeit, Eingabegeräte und visuelle Rückmeldungen zu testen.

🛠️ Funktionen

	•	KVM-Simulation:
	•	Simuliert Tastatur- und Mauseingaben (HID).
	•	Sende Bewegungen, Klicks und Tastenanschläge direkt an das Zielsystem.
	•	Bildschirm-Capturing:
	•	Zeigt Live-Frames von einer angeschlossenen Kamera an.
	•	Unterstützt Echtzeit-Anzeige ohne merkbare Verzögerung.
	•	Benutzerfreundlichkeit:
	•	Kompatibel mit Linux und macOS.
	•	Unterstützt Plug-and-Play für USB-Geräte.

📦 Installation

Voraussetzungen

	•	Python 3.9 oder höher.
	•	Abhängigkeiten:
	•	pygame
	•	opencv-python
	•	pyserial

Installiere die Abhängigkeiten mit:

pip install -r requirements.txt

🚀 Verwendung

	1.	Starte die Anwendung:

python main.py


	2.	Funktionen testen:
	•	Verbinde HID-Geräte und eine USB-Kamera.
	•	Teste Maus- und Tastatureingaben im Pygame-Fenster.
	3.	App beenden:
	•	Drücke Ctrl + C oder schließe das Fenster.

⚙️ Konfiguration

HID-Geräte

Die App sucht automatisch nach USB-Serial-Geräten (usbserial, ttyUSB).

Kamera

Die erste verfügbare Kamera (/dev/video0 oder ID 0) wird standardmäßig verwendet. Um eine andere Kamera zu verwenden, passe die ID in main.py an:

cap = cv2.VideoCapture(<CAMERA_ID>)

🖥️ Screenshots

Bild: Beispielansicht der PyVIC-Oberfläche.

👥 Beitragende

	•	[Dmitry Eisen] – Projektentwickler
	•	Vorschläge und Beiträge willkommen! Öffne ein Issue oder erstelle einen Pull-Request.

📄 Lizenz

Dieses Projekt steht unter der MIT-Lizenz. Weitere Details findest du in der Datei LICENSE.

GitHub: PyVIC Repository
