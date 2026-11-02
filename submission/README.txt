{app} {version} - 2D potential flow simulator
ME 470 Introduction to Aerodynamics - Semester Project 1 (Fall 2026-2027)
Mahmut Tunay Bacaksiz, 300203046 - Izmir Institute of Technology, Department of Mechanical Engineering


CONTENTS

  1_Report.pdf        the report (equations, architecture, validation, examples)
  2_User_Guide.pdf    how to use the program
  3_Program\          {program_line}
  4_Source_Code\      the source code of the program (Python)
  5_Verification\     the program's verification report: open verification.html (any web browser).
                      figures\ holds its figures as separate images; other_formats_optional\ holds the same
                      tables as plain text (.md) and as data (.csv) - not needed for reading the report.


RUNNING THE PROGRAM (Windows 10 / 11)

  Nothing has to be installed: no Python, no libraries, no internet connection.
  Everything the program needs is inside its folder.

{program_steps}

  The first start takes 15-30 s (the program prepares its fast calculations once); later starts take a
  few seconds.
  The assignment's verification cases: menu Presets -> Verification cases (assignment).
  Inside the program: Help -> User guide (F1) and Help -> Run verification.


RUNNING FROM THE SOURCE CODE (optional; Windows, macOS or Linux)

  Not needed for the program above - only to run or read the Python code itself.

  1. Install Python 3.13 from https://www.python.org/downloads/
     (Windows: tick "Add python.exe to PATH" on the first page of the installer).
  2. Open a terminal in the 4_Source_Code folder
     (Windows: open the folder in File Explorer, click the address bar, type cmd, press Enter).
  3. Install the libraries the program uses (once; needs an internet connection):
         python -m pip install -r requirements.txt
  4. Start the program:
         python main.py

  Also possible:
         python main.py --verify          writes the verification report to the folder verification\
         python -m pip install pytest     then:   python -m pytest     runs the automatic tests (tests\)
