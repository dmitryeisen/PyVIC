# PyVIC

![](/assets/pyvic.png)

PyVIC (Python Virtual Input Console) is an application for simulating HID devices (keyboard and mouse) and displaying real-time screen data via camera capturing. This tool provides a simple way to test input devices and visual feedback.

🛠️ Features

	•	KVM Simulation:
	•	Simulates keyboard and mouse inputs (HID).
	•	Sends movements, clicks, and keystrokes directly to the target system.
	•	Screen Capturing:
	•	Displays live frames from a connected camera.
	•	Supports real-time display without noticeable delay.
	•	User-Friendly:
	•	Compatible with Linux and macOS.
	•	Supports plug-and-play for USB devices.

📦 Installation

Requirements

Python 3.9 or higher.

Dependencies:

	•	pygame
	•	opencv-python
	•	pyserial

Install dependencies with:

    pip install -r requirements.txt

🚀 Usage

Start the application:

    python main.py


Test functionality:
    •	Connect HID devices and a USB camera.
    •	Test mouse and keyboard inputs in the Pygame window. 
Exit the application:
    •	Press Ctrl + C or close the window.

⚙️ Configuration

HID Devices

The app automatically searches for USB serial devices (usbserial, ttyUSB).

Camera

The first available camera (/dev/video0 or ID 0) is used by default. To use another camera, modify the ID in main.py:

    cap = cv2.VideoCapture(<CAMERA_ID>)

🖥️ Screenshots

Image: Example view of the PyVIC interface.

👥 Contributors

	•	[Dmitry Eisen] – Project Developer
	•	Suggestions and contributions are welcome! Open an issue or submit a pull request.

📄 License

This project is licensed under the MIT License. For more details, see the LICENSE file.

GitHub: PyVIC Repository

🛠️ Planned Features

We are working to enhance PyVIC with the following features:

	•	Cross-Platform Compatibility:
	•	Improved support for Windows-based systems.
	•	Customizable key mappings via configuration files.
	•	German Keyboard Layout:
	•	Extended support for German keyboard layout mapping, ensuring accurate input for special characters and regional key configurations.

How to Contribute

If you have ideas, suggestions, or want to help implement these features, feel free to open an issue or submit a pull request in the GitHub repository!