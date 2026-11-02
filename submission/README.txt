{app} {version} - 2D potential flow simulator
ME 470 Introduction to Aerodynamics - Semester Project 1 (Fall 2026-2027)
Mahmut Tunay Bacaksiz, 300203046 - Izmir Institute of Technology, Department of Mechanical Engineering


CONTENTS

  1_Report.pdf        the report (equations, architecture, validation, examples)
  2_User_Guide.pdf    how to use the program
  3_Program\          {program_line}
  4_Source_Code\      the complete source code (Python)
  5_Verification\     the program's own verification report: verification.html (open it in a browser),
                      the same as .md and .csv, and its figures


RUNNING THE PROGRAM (Windows 10 / 11, no Python needed)

{program_steps}

  The first start takes 15-30 s (the fast kernels are compiled once); later starts take a few seconds.
  The assignment's verification cases: Presets -> 1 Verification cases (assignment).
  Help -> User guide (F1) and Help -> Run verification are inside the program.


RUNNING FROM THE SOURCE CODE (Windows, macOS or Linux; Python 3.11 - 3.13)

  cd 4_Source_Code
  python -m pip install -r requirements.txt
  python main.py                   the program
  python main.py --verify          the verification report (written to verification\)
  python -m pip install -r requirements-dev.txt
  python -m pytest                 the automatic tests
